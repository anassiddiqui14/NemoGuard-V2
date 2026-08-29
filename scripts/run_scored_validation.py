#!/usr/bin/env python3
"""
WP-029-001 -- Scored Validation Benchmark CLI runner.

Live-triggers real scenarios from src/domain/evaluation/ground_truth.py
against the real running stack (real API, real Postgres, real NVIDIA
LLM, and -- for scenarios with a trigger_endpoint -- the real Scenario
Lab simulator / LocalStack), waits for the real multi-agent pipeline to
reach a terminal state, fetches the REAL persisted hypotheses/plan/
verification results via the real API, scores them against ground
truth (src/domain/evaluation/scoring.py), and persists results
(src/domain/evaluation/scored_validation_store.py).

This intentionally reuses the exact same real trigger + poll mechanics
already proven live in scripts/run_ai_evaluation.py and
scripts/scenario_matrix.py -- it does not introduce a second, simplified
harness.

Usage:
    python3 scripts/run_scored_validation.py --scenario all
    python3 scripts/run_scored_validation.py --scenario INGEST-SCHEMA-DRIFT
    python3 scripts/run_scored_validation.py --scenario all --model nvidia/nemotron-3-super-120b-a12b
    python3 scripts/run_scored_validation.py --scenario all --json --out docs/validation/scored_validation_result.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.domain.evaluation.ground_truth import SCENARIO_CATALOG, get_scenario, ScoredScenario
from src.domain.evaluation.scoring import ScenarioRunResult, score_scenario_run, ScenarioScore
from src.domain.evaluation.scored_validation_store import ScoredValidationStore

API_BASE = os.environ.get("NEMOGUARD_API_BASE", "http://localhost:8000")
SIM_BASE = os.environ.get("NEMOGUARD_SIM_BASE", "http://localhost:8001")
POLL_TIMEOUT_SEC = 360
POLL_INTERVAL_SEC = 4


class Harness:
    def __init__(self, http: httpx.Client):
        self.http = http
        self._token: Optional[str] = None

    def token(self) -> str:
        if self._token:
            return self._token
        r = self.http.get(f"{API_BASE}/api/v2/auth/mock-login?role=admin")
        r.raise_for_status()
        self._token = r.json()["access_token"]
        return self._token

    def h(self) -> dict:
        return {"Authorization": f"Bearer {self.token()}"}

    def list_incidents(self) -> List[dict]:
        r = self.http.get(f"{API_BASE}/api/v2/incidents?state=all", headers=self.h(), timeout=30.0)
        r.raise_for_status()
        return r.json()

    def incident_alert_count(self, incident_id: str) -> int:
        r = self.http.get(f"{API_BASE}/api/v2/incidents/{incident_id}/alerts", headers=self.h(), timeout=15.0)
        r.raise_for_status()
        return len(r.json())

    def hypotheses(self, incident_id: str) -> List[dict]:
        r = self.http.get(f"{API_BASE}/api/v2/incidents/{incident_id}/hypotheses", headers=self.h(), timeout=15.0)
        r.raise_for_status()
        return r.json()

    def evidence(self, incident_id: str) -> List[dict]:
        r = self.http.get(f"{API_BASE}/api/v2/incidents/{incident_id}/evidence", headers=self.h(), timeout=15.0)
        r.raise_for_status()
        return r.json()

    def plans(self, incident_id: str) -> List[dict]:
        r = self.http.get(f"{API_BASE}/api/v2/incidents/{incident_id}/plans", headers=self.h(), timeout=15.0)
        r.raise_for_status()
        return r.json()

    def approve_plan(self, incident_id: str, plan_id: str, plan_hash: str) -> dict:
        r = self.http.post(
            f"{API_BASE}/api/v2/incidents/{incident_id}/plans/{plan_id}/approve",
            headers=self.h(), timeout=180.0,
            json={"decision": "APPROVED", "plan_hash": plan_hash},
        )
        r.raise_for_status()
        return r.json()

    def incident(self, incident_id: str) -> Optional[dict]:
        for i in self.list_incidents():
            if i["incident_id"] == incident_id:
                return i
        return None

    def verification_results(self, incident_id: str) -> List[dict]:
        # No dedicated endpoint; reuse the evidence-package endpoint,
        # which already surfaces verification_result rows for real.
        r = self.http.get(f"{API_BASE}/api/v2/incidents/{incident_id}/evidence-package", headers=self.h(), timeout=20.0)
        r.raise_for_status()
        return r.json().get("verification_results", [])

    def lab_trigger(self, endpoint: str, scenario_name: str) -> dict:
        r = self.http.post(f"{SIM_BASE}/lab/trigger/{endpoint}", json={"scenario": scenario_name}, timeout=60.0)
        r.raise_for_status()
        return r.json()

    def cancel_incident(self, incident_id: str, reason: str) -> None:
        try:
            self.http.post(
                f"{API_BASE}/api/v2/incidents/{incident_id}/cancel",
                headers=self.h(), timeout=30.0, json={"reason": reason},
            )
        except Exception:
            pass

    def reset_alarm_to_ok(self, alarm_name: str) -> None:
        # Matches the exact same real reset mechanism already proven live
        # in scripts/run_ai_evaluation.py's Harness.reset_alarm_to_ok --
        # a real CloudWatch (LocalStack-emulated) set_alarm_state call.
        # Without this, a same-alarm scenario triggered again while the
        # alarm is still in ALARM state will correlate onto whatever
        # incident that alarm is already attached to instead of producing
        # a fresh, independently-scoreable incident.
        try:
            import boto3
            boto3.client(
                "cloudwatch", endpoint_url="http://localhost:4566",
                aws_access_key_id="test", aws_secret_access_key="test", region_name="us-east-1",
            ).set_alarm_state(AlarmName=alarm_name, StateValue="OK", StateReason="Reset by scored validation harness.")
        except Exception as e:
            print(f"  (warning: could not reset alarm {alarm_name}: {e})")


def run_one_scenario(h: Harness, scenario: ScoredScenario, model_name: Optional[str], prompt_version: str) -> ScenarioRunResult:
    run = ScenarioRunResult(scenario_id=scenario.scenario_id, model_name=model_name, prompt_version=prompt_version)
    start = time.monotonic()

    if not scenario.trigger_endpoint:
        # Pure diagnostic / correlation-assertion scenario with no direct
        # trigger mapping in this CLI (per the spec these require multi
        # -step manual sequences, e.g. CORRELATION-SAME-ALARM-NEW-INCIDENT
        # needs two separate triggers with an alarm reset between them).
        # Recorded honestly as skipped, never fabricated.
        run.trigger_failed = True
        run.trigger_error = "No single-trigger mapping for this scenario in this CLI version; requires a manual multi-step sequence."
        return run

    # Reset the alarm to OK before triggering, matching the same real
    # mechanism proven live in run_ai_evaluation.py. Without this, if this
    # scenario shares an alarm with a still-open incident from an earlier
    # run in the same session, the new alert deterministically correlates
    # onto that old incident instead of producing an independently
    # -scoreable one.
    if scenario.alarm_name:
        h.reset_alarm_to_ok(scenario.alarm_name)
        time.sleep(2)

    before_ids = {i["incident_id"] for i in h.list_incidents()}
    before_counts = {iid: h.incident_alert_count(iid) for iid in before_ids}

    try:
        h.lab_trigger(scenario.trigger_endpoint, scenario.trigger_scenario_name)
    except Exception as e:
        run.trigger_failed = True
        run.trigger_error = str(e)
        return run

    if scenario.diagnostic_only:
        # Healthy baselines: just confirm no NEW incident appeared.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            incidents = h.list_incidents()
            brand_new = [i for i in incidents if i["incident_id"] not in before_ids]
            if brand_new:
                run.incident_count_observed = len(brand_new)
                run.incident_id = brand_new[0]["incident_id"]
                break
            time.sleep(3)
        else:
            run.incident_count_observed = 0
        run.elapsed_seconds = round(time.monotonic() - start, 1)
        return run

    deadline = time.monotonic() + POLL_TIMEOUT_SEC
    incident_id: Optional[str] = None
    while time.monotonic() < deadline and not incident_id:
        try:
            incidents = h.list_incidents()
        except Exception:
            time.sleep(POLL_INTERVAL_SEC)
            continue
        brand_new = [i for i in incidents if i["incident_id"] not in before_ids]
        if brand_new:
            incident_id = brand_new[0]["incident_id"]
            break
        for i in incidents:
            iid = i["incident_id"]
            if iid in before_counts:
                try:
                    if h.incident_alert_count(iid) > before_counts[iid]:
                        incident_id = iid
                        break
                except Exception:
                    pass
        if incident_id:
            break
        time.sleep(POLL_INTERVAL_SEC)

    if not incident_id:
        run.trigger_failed = True
        run.trigger_error = f"No incident observed within {POLL_TIMEOUT_SEC}s"
        run.elapsed_seconds = round(time.monotonic() - start, 1)
        return run

    run.incident_id = incident_id
    run.incident_count_observed = 1

    # Poll for hypotheses AND a terminal-ish status (PLAN_READY, NEEDS_REVIEW,
    # MANUAL_ACTION_REQUIRED, RESOLVED, FAILED) so we score the real final
    # investigation output, not a half-finished snapshot.
    terminal_statuses = {"PLAN_READY", "NEEDS_REVIEW", "MANUAL_ACTION_REQUIRED", "RESOLVED", "FAILED", "AWAITING_APPROVAL", "EXECUTING", "VERIFYING"}
    hyps: List[dict] = []
    incident_row: Optional[dict] = None
    while time.monotonic() < deadline:
        try:
            hyps = h.hypotheses(incident_id)
            incident_row = h.incident(incident_id)
        except Exception:
            hyps, incident_row = [], None
        if hyps and incident_row and incident_row.get("status") in terminal_statuses:
            break
        time.sleep(POLL_INTERVAL_SEC)

    run.hypotheses = hyps
    run.final_status = incident_row.get("status") if incident_row else None
    run.primary_resource_observed = (incident_row.get("primary_job_id") or incident_row.get("title") or "") if incident_row else None

    try:
        run.evidence = h.evidence(incident_id)
    except Exception:
        pass

    plan_id_for_approval: Optional[str] = None
    plan_hash_for_approval: Optional[str] = None
    try:
        plans = h.plans(incident_id)
        if plans:
            latest = plans[0]
            run.plan_risk = latest.get("overall_risk")
            plan_id_for_approval = latest.get("action_plan_id")
            plan_hash_for_approval = latest.get("plan_hash")
    except Exception:
        pass

    # If the plan reached a real review-ready state (PENDING_APPROVAL --
    # i.e. the Grounding Critic did NOT flag it NEEDS_REVIEW), approve it
    # for real through the exact same governed approval endpoint a human
    # operator would use, so the benchmark can genuinely exercise
    # execution + independent verification, not just stop at RCA. A plan
    # marked NEEDS_REVIEW is deliberately NOT auto-approved here -- that
    # human safety gate is exactly what this benchmark must never bypass.
    if plan_id_for_approval and plan_hash_for_approval and run.final_status in ("PLAN_READY", "AWAITING_APPROVAL"):
        try:
            with_plans = h.plans(incident_id)
            current_plan = next((p for p in with_plans if p.get("action_plan_id") == plan_id_for_approval), None)
            if current_plan and current_plan.get("status") == "PENDING_APPROVAL":
                h.approve_plan(incident_id, plan_id_for_approval, plan_hash_for_approval)
                # Wait for execution + independent verification to reach a
                # real terminal state.
                exec_deadline = time.monotonic() + POLL_TIMEOUT_SEC
                while time.monotonic() < exec_deadline:
                    incident_row = h.incident(incident_id)
                    if incident_row and incident_row.get("status") in ("RESOLVED", "FAILED"):
                        break
                    time.sleep(POLL_INTERVAL_SEC)
                if incident_row:
                    run.final_status = incident_row.get("status")
        except Exception as e:
            run.error = f"approval/execution step failed: {e}"

    run.elapsed_seconds = round(time.monotonic() - start, 1)

    try:
        plans = h.plans(incident_id)
        if plans:
            latest = plans[0]
            run.plan_capabilities_used = [
                s.get("capability_id") for s in latest.get("steps", []) if s.get("capability_id")
            ]
    except Exception:
        pass
    try:
        run.verification_results = h.verification_results(incident_id)
    except Exception:
        pass

    return run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="all", help="scenario_id, or 'all'")
    parser.add_argument("--model", default=None, help="model_name to record (informational; live scenarios use the deployed API's default model)")
    parser.add_argument("--prompt-version", default="v1")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    if args.scenario == "all":
        scenarios = SCENARIO_CATALOG
    else:
        scenarios = [get_scenario(args.scenario)]

    store = ScoredValidationStore()
    run_id = store.start_run(model_name=args.model, prompt_version=args.prompt_version, total_scenarios=len(scenarios))
    print(f"Scored validation run: {run_id} ({len(scenarios)} scenario(s))")

    with httpx.Client() as http_client:
        h = Harness(http_client)
        scores: List[ScenarioScore] = []
        for scenario in scenarios:
            print(f"\n=== {scenario.scenario_id} ({scenario.category}) ===")
            run = run_one_scenario(h, scenario, args.model, args.prompt_version)
            score = score_scenario_run(scenario, run)
            store.record_score(run_id, score, incident_id=run.incident_id)
            scores.append(score)

            if run.trigger_failed:
                print(f"  SKIPPED/FAILED: {run.trigger_error}")
            else:
                print(f"  incident_id={run.incident_id} final_status={run.final_status} elapsed={run.elapsed_seconds}s")
                print(f"  top1_correct={score.top1_correct} top3_correct={score.top3_correct} "
                      f"terminal_state_correct={score.terminal_state_correct} "
                      f"verification_correct={score.verification_correct} false_resolution={score.false_resolution}")
                for note in score.notes:
                    print(f"  - {note}")

    store.complete_run(run_id)
    scorecard = store.get_scorecard(run_id)

    print("\n" + "=" * 70)
    print("SCORECARD")
    print("=" * 70)
    for k, v in scorecard.items():
        print(f"  {k}: {v}")

    if args.json or args.out:
        payload = {"run_id": run_id, "scorecard": scorecard, "scores": [s.to_dict() for s in scores]}
        if args.out:
            os.makedirs(os.path.dirname(args.out), exist_ok=True) if os.path.dirname(args.out) else None
            with open(args.out, "w") as f:
                json.dump(payload, f, indent=2, default=str)
            print(f"\nWrote JSON report to {args.out}")
        if args.json and not args.out:
            print(json.dumps(payload, indent=2, default=str))

    return 1 if scorecard.get("false_resolution_count", 0) > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
