#!/usr/bin/env python3
"""
WP-VAL-002 — Repeatable Scenario Test Harness.

Turns manual "click a cockpit button and eyeball the result" demos into a
deterministic, scriptable validation suite. Each scenario:

  1. triggers a REAL failure (via simulator_backend's /lab/trigger/* — the
     same LocalStack-backed Lambda/S3/CloudWatch chain the Scenario Cockpit
     UI uses, not a hand-scripted webhook payload)
  2. polls NemoGuard's real API until the resulting incident reaches an
     observable state or a timeout elapses
  3. asserts against expected outcomes (a new incident was created, its
     status/severity is sane, etc.)
  4. persists a structured JSON result record (see APP_STATUS_REPORT's
     linked validation plan §32 for the target result schema)

This intentionally does NOT try to assert exact RCA root-cause text or
approve/execute a plan end-to-end yet -- those require a real LLM round
trip whose wording is not byte-for-byte deterministic. This harness proves
the INFRASTRUCTURE of validation (trigger -> observe -> assert -> persist)
works repeatably; WP-VAL-004's AI evaluation benchmark is the correct place
for RCA-accuracy scoring against ground truth.

Usage:
    python3 scripts/run_validation_suite.py --suite core
    python3 scripts/run_validation_suite.py --suite core --json
    python3 scripts/run_validation_suite.py --suite core --api-base http://localhost:8000 --sim-base http://localhost:8001
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import httpx


# --------------------------------------------------------------------------
# Scenario definitions
# --------------------------------------------------------------------------

@dataclass
class ScenarioResult:
    scenario_id: str
    title: str
    run_id: str = ""
    started_at: str = ""
    completed_at: str = ""
    trigger_ok: bool = False
    incident_created: bool = False
    incident_id: Optional[str] = None
    final_status: Optional[str] = None
    expected_terminal_states: list[str] = field(default_factory=list)
    passed: bool = False
    failure_reason: Optional[str] = None
    poll_seconds: float = 0.0


@dataclass
class Scenario:
    scenario_id: str
    title: str
    # Function that fires the real trigger via the simulator's /lab/trigger
    # endpoints; returns the run_id the Lambda/job used so we can find the
    # resulting incident even if correlation attaches it under a different
    # incident_id than a brand-new one.
    trigger: Callable[["Harness"], dict]
    # States considered a successful, expected observable outcome for this
    # scenario. INVESTIGATING is the expected immediate post-trigger state
    # for a genuinely NEW incident; the harness does not wait for full
    # RCA/plan/approval to complete (see module docstring).
    expected_states: list[str]
    poll_timeout_seconds: int = 90
    # The CloudWatch alarm this scenario's Lambda failure trips. When set,
    # the harness resets it to OK immediately before triggering, so a
    # scenario sharing an alarm with one already run earlier in the same
    # suite still gets a genuine OK->ALARM transition (and therefore a
    # real SNS notification) instead of a no-op "still in ALARM" breach.
    alarm_name: Optional[str] = None


class Harness:
    def __init__(self, api_base: str, sim_base: str, http: httpx.Client):
        self.api_base = api_base.rstrip("/")
        self.sim_base = sim_base.rstrip("/")
        self.http = http
        self._token: Optional[str] = None

    def token(self) -> str:
        if self._token:
            return self._token
        r = self.http.get(f"{self.api_base}/api/v2/auth/mock-login?role=commander")
        r.raise_for_status()
        self._token = r.json()["access_token"]
        return self._token

    def auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token()}"}

    def lab_trigger(self, endpoint: str, scenario: str) -> dict:
        r = self.http.post(f"{self.sim_base}/lab/trigger/{endpoint}", json={"scenario": scenario}, timeout=60.0)
        r.raise_for_status()
        return r.json()

    def list_incidents(self) -> list[dict]:
        r = self.http.get(f"{self.api_base}/api/v2/incidents?state=all", headers=self.auth_headers(), timeout=30.0)
        r.raise_for_status()
        return r.json()

    def incident_alert_count(self, incident_id: str) -> int:
        r = self.http.get(
            f"{self.api_base}/api/v2/incidents/{incident_id}/alerts",
            headers=self.auth_headers(),
            timeout=15.0,
        )
        r.raise_for_status()
        return len(r.json())

    def lab_status(self) -> dict:
        r = self.http.get(f"{self.sim_base}/lab/status", timeout=10.0)
        r.raise_for_status()
        return r.json()

    def reset_alarm_to_ok(self, alarm_name: str) -> None:
        """Forces a CloudWatch alarm back to OK state before a scenario that
        shares an alarm name with one already triggered in this run.

        CloudWatch only publishes an SNS notification on a genuine state
        TRANSITION (e.g. OK -> ALARM), not on every subsequent metric
        breach while an alarm is already sitting in ALARM state. Multiple
        of this suite's scenarios (schema_drift / oom_crash / db_outage)
        intentionally share the single `nemoguard-ingest-job-errors` alarm
        (they are different failure modes of the SAME Lambda function), so
        without this reset, only the FIRST scenario run in a suite would
        ever produce a new incident -- every subsequent same-alarm scenario
        would appear to "fail" for a reason that has nothing to do with
        NemoGuard's own correctness. This was discovered live during this
        harness's first real run (see docs/APP_STATUS_REPORT and the
        WP-VAL-002 commit message for the full root-cause trace) and is
        deliberately handled here rather than silently worked around.
        """
        try:
            self._aws_client("cloudwatch").set_alarm_state(
                AlarmName=alarm_name,
                StateValue="OK",
                StateReason="Reset to OK by validation harness before next scenario run.",
            )
        except Exception as e:
            print(f"  (warning: could not reset alarm {alarm_name} to OK: {e})")

    def _aws_client(self, service: str):
        import boto3
        return boto3.client(
            service,
            endpoint_url="http://localhost:4566",
            aws_access_key_id="test",
            aws_secret_access_key="test",
            region_name="us-east-1",
        )


def _trigger_ingest(scenario_name: str):
    def _run(h: Harness) -> dict:
        return h.lab_trigger("ingest", scenario_name)
    return _run


def _trigger_order_events(scenario_name: str):
    def _run(h: Harness) -> dict:
        return h.lab_trigger("order_events", scenario_name)
    return _run


def _trigger_notification(scenario_name: str):
    def _run(h: Harness) -> dict:
        return h.lab_trigger("notification", scenario_name)
    return _run


CORE_SUITE: list[Scenario] = [
    Scenario(
        scenario_id="VAL-SCHEMA-DRIFT-001",
        title="Schema Drift (real Lambda KeyError -> real CloudWatch alarm)",
        trigger=_trigger_ingest("schema_drift"),
        expected_states=["INVESTIGATING", "PLAN_READY", "AWAITING_APPROVAL"],
        alarm_name="nemoguard-ingest-job-errors",
    ),
    Scenario(
        scenario_id="VAL-OOM-CRASH-001",
        title="OOM Crash (real MemoryError inside the Lambda)",
        trigger=_trigger_ingest("oom_crash"),
        expected_states=["INVESTIGATING", "PLAN_READY", "AWAITING_APPROVAL"],
        # Shares nemoguard-ingest-job-errors with schema_drift above --
        # requires the OK reset (see Harness.reset_alarm_to_ok) or this
        # scenario will never produce a fresh SNS notification.
        alarm_name="nemoguard-ingest-job-errors",
    ),
    Scenario(
        scenario_id="VAL-DB-OUTAGE-001",
        title="DB Outage (real connection failure from the job)",
        trigger=_trigger_ingest("db_outage"),
        expected_states=["INVESTIGATING", "PLAN_READY", "AWAITING_APPROVAL"],
        alarm_name="nemoguard-ingest-job-errors",
    ),
    Scenario(
        scenario_id="VAL-PARTIAL-WRITE-001",
        title="Partial Write Crash (Glue-style mid-batch crash)",
        trigger=_trigger_order_events("partial_write_crash"),
        expected_states=["INVESTIGATING", "PLAN_READY", "AWAITING_APPROVAL"],
        alarm_name="nemoguard-order-events-job-errors",
    ),
    Scenario(
        scenario_id="VAL-POISON-PILL-001",
        title="Poison Pill (malformed SQS message)",
        trigger=_trigger_notification("poison_pill"),
        expected_states=["INVESTIGATING", "PLAN_READY", "AWAITING_APPROVAL"],
        # This DOES go through the same CloudWatch alarm -> SNS -> SQS ->
        # forwarder chain as the other scenarios (nemoguard-notification-job
        # -errors) -- an earlier version of this comment incorrectly
        # assumed otherwise. Live evidence from this harness's first run
        # showed the resulting incident (INC-ADD7EF57) was created only
        # ~1s after a too-short 30s timeout had already elapsed and marked
        # this scenario FAILED. 60s gives the alarm evaluation period and
        # forwarder poll loop realistic headroom.
        poll_timeout_seconds=90,
        alarm_name="nemoguard-notification-job-errors",
    ),
]

SUITES = {"core": CORE_SUITE}


def run_scenario(h: Harness, scenario: Scenario) -> ScenarioResult:
    result = ScenarioResult(
        scenario_id=scenario.scenario_id,
        title=scenario.title,
        expected_terminal_states=scenario.expected_states,
    )
    result.started_at = datetime.now(timezone.utc).isoformat()
    poll_start = time.monotonic()

    before_snapshot = {i["incident_id"]: i["status"] for i in h.list_incidents()}
    before_ids = set(before_snapshot.keys())

    if scenario.alarm_name:
        h.reset_alarm_to_ok(scenario.alarm_name)
        # Give LocalStack's CloudWatch emulator a moment to persist the
        # state change before the trigger's metric breach is evaluated,
        # otherwise the reset can race the subsequent Lambda invocation.
        time.sleep(2)

    try:
        trigger_result = scenario.trigger(h)
        result.run_id = trigger_result.get("run_id", "")
        result.trigger_ok = trigger_result.get("function_error") is not None or "run_id" in trigger_result
    except Exception as e:
        result.failure_reason = f"trigger failed: {e}"
        result.completed_at = datetime.now(timezone.utc).isoformat()
        return result

    # Success is observed as EITHER a genuinely new incident, OR a real
    # alert being correlated into an existing OPEN incident (its alert
    # COUNT growing -- NOT its status, which correlation alone does not
    # change; only save_agent_findings/triage transitions do). Treating
    # only "brand-new incident_id" as success was a real bug in this
    # harness's first version: when a scenario shares an alarm/job with one
    # triggered earlier in the same suite run (e.g. schema_drift and
    # db_outage both hit nemoguard-ingest-job's single incident), NemoGuard's
    # correlator CORRECTLY attaches the new alert to the existing open
    # incident rather than creating a duplicate -- this is the desired,
    # real production behavior (see the terminal-incident-correlation fix
    # from WP-VAL-001), not a failure to detect anything. A first attempt
    # at fixing this checked incident.status for a change, but correlation
    # (orchestrator.py's process_webhook "Map to existing incident" path)
    # only appends an incident_alert row and updates summary/updated_at --
    # it does NOT change status. Live evidence confirmed 3 alerts
    # (schema_drift + oom_crash + db_outage) all attached to the SAME
    # incident with its status unchanged at INVESTIGATING throughout.
    before_alert_counts: dict[str, int] = {
        iid: h.incident_alert_count(iid) for iid in before_ids
    }

    deadline = time.monotonic() + scenario.poll_timeout_seconds
    observed_incident: Optional[dict] = None
    while time.monotonic() < deadline:
        try:
            incidents = h.list_incidents()
        except Exception:
            time.sleep(3)
            continue

        brand_new = [i for i in incidents if i["incident_id"] not in before_ids]
        if brand_new:
            observed_incident = brand_new[0]
            break

        for i in incidents:
            iid = i["incident_id"]
            if iid not in before_alert_counts:
                continue
            try:
                current_count = h.incident_alert_count(iid)
            except Exception:
                continue
            if current_count > before_alert_counts[iid]:
                observed_incident = i
                break
        if observed_incident:
            break

        time.sleep(3)

    result.poll_seconds = round(time.monotonic() - poll_start, 1)
    result.completed_at = datetime.now(timezone.utc).isoformat()

    if not observed_incident:
        result.failure_reason = (
            f"no new incident and no existing-incident state change observed within "
            f"{scenario.poll_timeout_seconds}s (run_id={result.run_id or 'unknown'})"
        )
        result.passed = False
        return result

    result.incident_created = observed_incident["incident_id"] not in before_ids
    result.incident_id = observed_incident["incident_id"]
    result.final_status = observed_incident["status"]
    result.passed = result.final_status in scenario.expected_states
    if not result.passed:
        result.failure_reason = (
            f"incident {result.incident_id} reached status={result.final_status}, "
            f"expected one of {scenario.expected_states}"
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the NemoGuard repeatable scenario validation suite.")
    parser.add_argument("--suite", default="core", choices=list(SUITES.keys()))
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--sim-base", default="http://localhost:8001")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of a human table.")
    parser.add_argument(
        "--out",
        default=None,
        help="Optional path to also write the full JSON result set to disk.",
    )
    args = parser.parse_args()

    with httpx.Client() as http:
        harness = Harness(args.api_base, args.sim_base, http)

        try:
            lab = harness.lab_status()
        except Exception as e:
            print(f"FATAL: could not reach simulator at {args.sim_base}: {e}", file=sys.stderr)
            return 2
        if not lab.get("available"):
            print(f"FATAL: LocalStack lab not available: {lab.get('detail')}", file=sys.stderr)
            return 2

        scenarios = SUITES[args.suite]
        results: list[ScenarioResult] = []
        for scenario in scenarios:
            if not args.json:
                print(f"Running {scenario.scenario_id}: {scenario.title} ...", flush=True)
            result = run_scenario(harness, scenario)
            results.append(result)
            if not args.json:
                status = "PASS" if result.passed else "FAIL"
                detail = result.failure_reason or f"incident={result.incident_id} status={result.final_status}"
                print(f"  [{status}] {detail} ({result.poll_seconds}s)")

        passed_count = sum(1 for r in results if r.passed)
        total = len(results)

        if args.json:
            print(json.dumps({"suite": args.suite, "results": [asdict(r) for r in results], "passed": passed_count, "total": total}, indent=2))
        else:
            print()
            for r in results:
                mark = "PASS" if r.passed else "FAIL"
                print(f"{r.scenario_id:<28} {mark}")
            print(f"\n{passed_count}/{total} PASS")

        if args.out:
            with open(args.out, "w") as f:
                json.dump(
                    {
                        "suite": args.suite,
                        "run_at": datetime.now(timezone.utc).isoformat(),
                        "results": [asdict(r) for r in results],
                        "passed": passed_count,
                        "total": total,
                    },
                    f,
                    indent=2,
                )
            if not args.json:
                print(f"\nWrote results to {args.out}")

        return 0 if passed_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
