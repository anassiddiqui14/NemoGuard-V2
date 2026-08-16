#!/usr/bin/env python3
"""
End-to-end agent evaluation harness against the LocalStack lab.

For each real failure scenario (schema drift, partial write, poison-pill
queue backup, orchestrated pipeline step failure), this script:
  1. Triggers the REAL failure (via the corresponding break_*.py script's
     logic, reused directly here) against real Lambda/SQS/Step Functions
     resources.
  2. Waits for the forwarder-created incident to appear via NemoGuard's own
     API (the forwarder must already be running separately -- see below).
  3. Triggers /triage on that incident.
  4. Polls until a plan exists, then GRADES the agents' actual output
     against scenario-specific expected criteria (e.g. "did the plan call
     check_table_staleness before proposing a rerun?", "did RCA correctly
     identify the missing field?").
  5. Prints a pass/fail report per scenario plus an overall score.

Prerequisites (run these first, in separate terminals):
  docker compose --profile lab up -d localstack
  python3 localstack_lab/provision.py
  python3 localstack_lab/forwarder.py   (leave running)
  python3 data/runbook_docs/generate_docs.py
  (NemoGuard API running with NEMOGUARD_LOCALSTACK_LAB=1)

Usage:
    python3 scripts/run_agent_evaluation.py
    python3 scripts/run_agent_evaluation.py --scenario schema_drift
"""

import argparse
import json
import os
import sys
import time
import uuid

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "localstack_lab"))
from aws_clients import client  # noqa: E402

NEMOGUARD_API_BASE = os.environ.get("NEMOGUARD_API_BASE", "http://localhost:8000")
BUCKET_NAME = "nemoguard-lab-data"
POLL_TIMEOUT_SEC = 90
POLL_INTERVAL_SEC = 3


def _get_admin_token() -> str:
    r = httpx.get(f"{NEMOGUARD_API_BASE}/api/v2/auth/mock-login", params={"role": "admin"}, timeout=15)
    r.raise_for_status()
    return r.json()["access_token"]


def _wait_for_new_incident(token: str, before_ids: set, timeout_sec: int = POLL_TIMEOUT_SEC) -> dict | None:
    """Polls the incidents list until a genuinely NEW incident_id shows up
    (one not present in before_ids) -- this connects a just-triggered real
    failure to the specific incident row the forwarder created for it."""
    deadline = time.time() + timeout_sec
    headers = {"Authorization": f"Bearer {token}"}
    while time.time() < deadline:
        r = httpx.get(f"{NEMOGUARD_API_BASE}/api/v2/incidents", params={"state": "all"}, headers=headers, timeout=15)
        if r.status_code == 200:
            incidents = r.json()
            for inc in incidents:
                if inc["incident_id"] not in before_ids:
                    return inc
        time.sleep(POLL_INTERVAL_SEC)
    return None


def _get_all_incident_ids(token: str) -> set:
    headers = {"Authorization": f"Bearer {token}"}
    r = httpx.get(f"{NEMOGUARD_API_BASE}/api/v2/incidents", params={"state": "all"}, headers=headers, timeout=15)
    r.raise_for_status()
    return {i["incident_id"] for i in r.json()}


def _trigger_triage(token: str, incident_id: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    r = httpx.post(f"{NEMOGUARD_API_BASE}/api/v2/incidents/{incident_id}/triage", headers=headers, timeout=15)
    if r.status_code not in (200, 202):
        print(f"  !! triage trigger returned {r.status_code}: {r.text}")


def _wait_for_plan(token: str, incident_id: str, timeout_sec: int = POLL_TIMEOUT_SEC) -> dict | None:
    deadline = time.time() + timeout_sec
    headers = {"Authorization": f"Bearer {token}"}
    while time.time() < deadline:
        r = httpx.get(f"{NEMOGUARD_API_BASE}/api/v2/incidents/{incident_id}/plans", headers=headers, timeout=15)
        if r.status_code == 200:
            plans = r.json()
            if plans:
                return plans[0]
        time.sleep(POLL_INTERVAL_SEC)
    return None


def _wait_for_hypotheses(token: str, incident_id: str, timeout_sec: int = POLL_TIMEOUT_SEC) -> list:
    deadline = time.time() + timeout_sec
    headers = {"Authorization": f"Bearer {token}"}
    while time.time() < deadline:
        r = httpx.get(f"{NEMOGUARD_API_BASE}/api/v2/incidents/{incident_id}/hypotheses", headers=headers, timeout=15)
        if r.status_code == 200:
            hyps = r.json()
            if hyps:
                return hyps
        time.sleep(POLL_INTERVAL_SEC)
    return []


def _stage_ingest_object(scenario: str) -> str:
    from break_scenario import SCENARIOS as INGEST_SCENARIOS  # noqa

    uid = uuid.uuid4().hex[:6]
    record = json.loads(json.dumps(INGEST_SCENARIOS[scenario]).replace("{uid}", uid))
    key = f"customer_profile/EVAL-{scenario}-{uid}.json"
    s3 = client("s3")
    s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=json.dumps(record).encode())
    lam = client("lambda")
    lam.invoke(FunctionName="nemoguard-ingest-job", InvocationType="Event",
               Payload=json.dumps({"bucket": BUCKET_NAME, "key": key}).encode())
    return key


def _stage_order_events_crash() -> None:
    from break_order_events_scenario import main as break_order_events_main  # noqa
    break_order_events_main()


def _stage_notification_poison_pill() -> None:
    lam = client("lambda")
    lam.invoke(FunctionName="nemoguard-notification-job", InvocationType="RequestResponse",
               Payload=json.dumps({"run_id": f"RUN-EVAL-notification-{uuid.uuid4().hex[:6]}",
                                    "message_body": {"simulate_poison_pill": True}}).encode())


def grade_schema_drift(hypotheses: list, plan: dict) -> dict:
    result = {"scenario": "schema_drift", "checks": []}
    hyp_text = " ".join(h.get("statement", "") + h.get("title", "") for h in hypotheses).lower()
    result["checks"].append(("RCA mentions schema/missing field", any(k in hyp_text for k in ["schema", "missing", "last_login_ip", "keyerror"])))
    steps_text = json.dumps(plan.get("steps", [])).lower() if plan else ""
    result["checks"].append(("Plan does NOT propose a naive blind retry with no diagnosis", "retry" not in steps_text or "escalat" in steps_text or "quarantine" in steps_text))
    return result


def grade_partial_write(hypotheses: list, plan: dict) -> dict:
    result = {"scenario": "partial_write", "checks": []}
    hyp_text = " ".join(h.get("statement", "") + h.get("title", "") for h in hypotheses).lower()
    result["checks"].append(("RCA mentions partial write/crash", any(k in hyp_text for k in ["partial", "crash", "order_events"])))
    steps_text = json.dumps(plan.get("steps", [])).lower() if plan else ""
    staleness_idx = steps_text.find("check_table_staleness")
    cleanup_idx = steps_text.find("cleanup_partial_write")
    rerun_idx = min([i for i in [steps_text.find("rerun"), steps_text.find("re-run")] if i >= 0], default=-1)
    result["checks"].append(("Plan calls check_table_staleness", staleness_idx >= 0))
    result["checks"].append(("Plan calls cleanup_partial_write before any rerun step", cleanup_idx >= 0 and (rerun_idx == -1 or cleanup_idx < rerun_idx)))
    return result


def grade_poison_pill(hypotheses: list, plan: dict) -> dict:
    result = {"scenario": "poison_pill", "checks": []}
    hyp_text = " ".join(h.get("statement", "") + h.get("title", "") for h in hypotheses).lower()
    result["checks"].append(("RCA mentions poison message / malformed message", any(k in hyp_text for k in ["poison", "malformed", "missing", "user_id"])))
    steps_text = json.dumps(plan.get("steps", [])).lower() if plan else ""
    result["checks"].append(("Plan does NOT propose purging the entire queue", "purge" not in steps_text))
    return result


def grade_pipeline(hypotheses: list, plan: dict) -> dict:
    result = {"scenario": "pipeline_step_failure", "checks": []}
    hyp_text = " ".join(h.get("statement", "") + h.get("title", "") for h in hypotheses).lower()
    result["checks"].append(("RCA identifies a specific failing state/step", any(k in hyp_text for k in ["state", "step", "ingest", "order_events", "pipeline"])))
    return result


SCENARIOS = {
    "schema_drift": {"stage": lambda: _stage_ingest_object("schema_drift"), "grade": grade_schema_drift},
    "partial_write": {"stage": _stage_order_events_crash, "grade": grade_partial_write},
    "poison_pill": {"stage": _stage_notification_poison_pill, "grade": grade_poison_pill},
}


def run_scenario(name: str, token: str) -> dict:
    print(f"\n{'=' * 60}\nSCENARIO: {name}\n{'=' * 60}")
    before_ids = _get_all_incident_ids(token)

    print("  Triggering real failure...")
    SCENARIOS[name]["stage"]()

    print("  Waiting for forwarder to create a new incident...")
    incident = _wait_for_new_incident(token, before_ids)
    if not incident:
        return {"scenario": name, "error": "No new incident appeared within timeout. Is the forwarder running?"}
    incident_id = incident["incident_id"]
    print(f"  New incident: {incident_id} -- {incident.get('title')}")

    print("  Triggering triage...")
    _trigger_triage(token, incident_id)

    print("  Waiting for hypotheses + plan...")
    hypotheses = _wait_for_hypotheses(token, incident_id)
    plan = _wait_for_plan(token, incident_id)

    if not hypotheses:
        return {"scenario": name, "incident_id": incident_id, "error": "No hypotheses produced within timeout."}
    if not plan:
        return {"scenario": name, "incident_id": incident_id, "error": "No plan produced within timeout.", "hypotheses": hypotheses}

    print(f"  Hypotheses: {len(hypotheses)} ranked, top confidence={hypotheses[0].get('confidence_score')}")
    print(f"  Plan: {plan.get('action_plan_id')} status={plan.get('status')} risk={plan.get('overall_risk')}")

    grade_result = SCENARIOS[name]["grade"](hypotheses, plan)
    grade_result["incident_id"] = incident_id
    return grade_result


def print_report(results: list) -> None:
    print(f"\n{'#' * 60}\nEVALUATION REPORT\n{'#' * 60}")
    total_checks = 0
    passed_checks = 0
    for res in results:
        print(f"\nScenario: {res['scenario']} (incident: {res.get('incident_id', 'N/A')})")
        if "error" in res:
            print(f"  ERROR: {res['error']}")
            continue
        for label, passed in res.get("checks", []):
            total_checks += 1
            passed_checks += 1 if passed else 0
            mark = "PASS" if passed else "FAIL"
            print(f"  [{mark}] {label}")
    print(f"\n{'-' * 60}")
    if total_checks > 0:
        pct = 100.0 * passed_checks / total_checks
        print(f"TOTAL: {passed_checks}/{total_checks} checks passed ({pct:.0f}%)")
    else:
        print("TOTAL: no checks were evaluated (all scenarios errored before grading).")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()), help="Run only this scenario.")
    args = parser.parse_args()

    print(f"Connecting to NemoGuard API at {NEMOGUARD_API_BASE} ...")
    token = _get_admin_token()
    print("Authenticated.")

    scenario_names = [args.scenario] if args.scenario else list(SCENARIOS.keys())
    results = []
    for name in scenario_names:
        try:
            results.append(run_scenario(name, token))
        except Exception as e:
            results.append({"scenario": name, "error": f"Unhandled exception: {e}"})

    print_report(results)


if __name__ == "__main__":
    main()
