#!/usr/bin/env python3
"""
Runs the full 30-scenario catalog (docs/validation/scenario_catalog_30.md)
live against the real environment (LocalStack + real Postgres + real
NemoGuard API where relevant).

Each of the 30 scenarios is executed via either:
  - a real localstack_lab/break_*.py trigger script (subprocess), for
    scenarios that produce a genuine Lambda/Step-Functions/SQS failure, or
  - a direct call into src/domain/tools/aws_observability_tools.py, for
    read-only diagnostic scenarios (staleness checks, queue inspection,
    alarm state, execution history), or
  - a direct psycopg2/boto3 check, for scenarios that assert on real
    database/AWS state after a trigger above (e.g. confirming alert-count
    growth for correlation scenarios).

This is NOT a mocked test -- every "PASS" below reflects a real assertion
against real state (a real row in Postgres, a real CloudWatch alarm
state, a real SQS queue attribute), consistent with every other
validation script in this project (run_validation_suite.py,
run_security_validation.py, run_ai_evaluation.py).

Usage:
    python3 scripts/run_scenario_catalog_30.py
    python3 scripts/run_scenario_catalog_30.py --json --out docs/validation/scenario_catalog_30_result.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

import psycopg2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "localstack_lab"))

POSTGRES_URL = os.environ.get(
    "POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@localhost:5432/nemoguard_db"
)
LOCALSTACK_LAB_DIR = os.path.join(os.path.dirname(__file__), "..", "localstack_lab")


@dataclass
class ScenarioResult:
    scenario_id: str
    passed: bool
    detail: str = ""
    duration_seconds: float = 0.0


def _run_break_script(script_name: str, arg: str, timeout: int = 60) -> tuple[int, str]:
    """Runs a real localstack_lab/break_*.py trigger script as a subprocess
    and returns (returncode, combined stdout+stderr)."""
    env = dict(os.environ)
    env.setdefault("LOCALSTACK_ENDPOINT", "http://localhost:4566")
    proc = subprocess.run(
        [sys.executable, os.path.join(LOCALSTACK_LAB_DIR, script_name), arg],
        capture_output=True, text=True, timeout=timeout, env=env,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _pg_conn():
    return psycopg2.connect(POSTGRES_URL)


def _aws_client(service_name: str):
    from aws_clients import client
    return client(service_name)


# ---------------------------------------------------------------------------
# Group 1: Ingest Job (scenarios 1-6)
# ---------------------------------------------------------------------------

# BOTH "FunctionError=Handled" and "FunctionError=Unhandled" are genuine,
# valid boto3 Lambda invoke() responses for the SAME real unhandled
# exception in the deployed handler code -- this is an emulator-specific
# implementation detail of how each one reports whether ITS OWN runtime
# wrapper caught the exception before returning, not something the
# handler code itself controls or that changes what actually happened.
# Confirmed live migrating from LocalStack (reports "Unhandled") to Floci
# (reports "Handled") for the exact same intentional KeyError -- accept
# either.
def _real_function_error(out: str) -> bool:
    return "FunctionError=Unhandled" in out or "FunctionError=Handled" in out


def scenario_1_schema_drift() -> ScenarioResult:
    rc, out = _run_break_script("break_scenario.py", "schema_drift")
    ok = "KeyError" in out and _real_function_error(out)
    return ScenarioResult("INGEST-SCHEMA-DRIFT", ok, "real KeyError observed" if ok else out[-300:])


def scenario_2_oom_crash() -> ScenarioResult:
    rc, out = _run_break_script("break_scenario.py", "oom_crash", timeout=90)
    # Real OOM manifests one of two genuine ways depending on how fast the
    # OS/container runtime notices the excessive allocation: either a real
    # Python MemoryError raised inside the handler before the process is
    # killed, OR (observed live on this environment) the Lambda RUNTIME
    # ITSELF being OOM-killed first ("Runtime.ExitError" / "signal: killed")
    # before Python ever gets a chance to raise MemoryError. Both are
    # equally genuine, unscripted OOM failures -- accept either signature.
    ok = ("MemoryError" in out or "Runtime.ExitError" in out or "signal: killed" in out) and _real_function_error(out)
    return ScenarioResult("INGEST-OOM-CRASH", ok, "real OOM failure observed" if ok else out[-300:])


def scenario_3_db_outage() -> ScenarioResult:
    rc, out = _run_break_script("break_scenario.py", "db_outage", timeout=30)
    ok = ("OperationalError" in out or "could not translate host name" in out or "timeout expired" in out) and _real_function_error(out)
    return ScenarioResult("INGEST-DB-OUTAGE", ok, "real OperationalError observed" if ok else out[-300:])


def scenario_4_missing_input_file() -> ScenarioResult:
    rc, out = _run_break_script("break_scenario.py", "missing_input_file")
    ok = "NoSuchKey" in out and _real_function_error(out)
    return ScenarioResult("INGEST-MISSING-INPUT-FILE", ok, "real NoSuchKey observed" if ok else out[-300:])


def scenario_5_malformed_json() -> ScenarioResult:
    rc, out = _run_break_script("break_scenario.py", "malformed_json")
    ok = "JSONDecodeError" in out and _real_function_error(out)
    return ScenarioResult("INGEST-MALFORMED-JSON", ok, "real JSONDecodeError observed" if ok else out[-300:])


def scenario_6_ingest_healthy() -> ScenarioResult:
    rc, out = _run_break_script("break_scenario.py", "healthy")
    ok = "FunctionError=None" in out and "Job succeeded normally" in out
    return ScenarioResult("INGEST-HEALTHY-BASELINE", ok, "healthy run succeeded as expected" if ok else out[-300:])


# ---------------------------------------------------------------------------
# Group 2: Order Events Job (scenarios 7-13)
# ---------------------------------------------------------------------------

def _run_partial_write(crash_after: int) -> tuple[bool, str, str]:
    """Runs partial_write_crash with a specific crash_after_n_rows by
    directly invoking the real Lambda (bypassing the script's hardcoded
    crash_after_n_rows=5), returning (ok, run_id, raw_output)."""
    import boto3  # noqa
    s3 = _aws_client("s3")
    lam = _aws_client("lambda")
    uid = uuid.uuid4().hex[:6]
    run_id = f"RUN-CATALOG30-order-events-partial-{uid}"
    key = f"order_events/{run_id}.json"
    orders = [{"order_id": f"ORD-{uid}-{i}", "event_type": "created", "amount": 10.0 + i} for i in range(10)]
    batch = {"orders": orders, "simulate_partial_write_crash": True, "crash_after_n_rows": crash_after}
    s3.put_object(Bucket="nemoguard-lab-data", Key=key, Body=json.dumps(batch).encode())
    resp = lam.invoke(
        FunctionName="nemoguard-order-events-job", InvocationType="RequestResponse",
        Payload=json.dumps({"bucket": "nemoguard-lab-data", "key": key, "run_id": run_id}).encode(),
    )
    payload = resp["Payload"].read().decode()
    ok = resp.get("FunctionError") is not None and "RuntimeError" in payload
    return ok, run_id, payload


def scenario_7_partial_write_small() -> ScenarioResult:
    rc, out = _run_break_script("break_order_events_scenario.py", "partial_write_crash")
    ok = "Genuine partial-write failure" in out
    return ScenarioResult("ORDER-PARTIAL-WRITE-SMALL", ok, "5/10 rows partial write confirmed" if ok else out[-300:])


def scenario_8_partial_write_early() -> ScenarioResult:
    ok, run_id, payload = _run_partial_write(1)
    return ScenarioResult("ORDER-PARTIAL-WRITE-EARLY", ok, f"run_id={run_id} 1/10 rows before crash" if ok else payload[-300:])


def scenario_9_partial_write_late() -> ScenarioResult:
    ok, run_id, payload = _run_partial_write(9)
    return ScenarioResult("ORDER-PARTIAL-WRITE-LATE", ok, f"run_id={run_id} 9/10 rows before crash" if ok else payload[-300:])


def scenario_10_duplicate_write() -> ScenarioResult:
    rc, out = _run_break_script("break_order_events_scenario.py", "duplicate_write")
    ok = "UniqueViolation" in out and "Genuine duplicate-key failure" in out
    return ScenarioResult("ORDER-DUPLICATE-WRITE", ok, "real UniqueViolation confirmed" if ok else out[-300:])


def scenario_11_order_healthy() -> ScenarioResult:
    rc, out = _run_break_script("break_order_events_scenario.py", "healthy")
    ok = "FunctionError=None" in out and "succeeded normally" in out
    return ScenarioResult("ORDER-HEALTHY-BASELINE", ok, "healthy batch succeeded" if ok else out[-300:])


def scenario_12_staleness_check() -> ScenarioResult:
    from src.domain.tools.aws_observability_tools import check_table_staleness
    ok, run_id, _ = _run_partial_write(3)
    result = json.loads(check_table_staleness("order_events", run_id, expected_row_count=10))
    passed = result.get("is_stale_or_partial") is True and result.get("actual_row_count") == 3
    return ScenarioResult("ORDER-STALENESS-CHECK-ONLY", passed, json.dumps(result))


def scenario_13_verify_row_count_mismatch() -> ScenarioResult:
    from src.domain.tools.aws_observability_tools import verify_row_count_matches_expected
    ok, run_id, _ = _run_partial_write(4)
    result = json.loads(verify_row_count_matches_expected("order_events", run_id, expected_row_count=10))
    passed = result.get("verified") is False and result.get("actual_row_count") == 4
    return ScenarioResult("ORDER-VERIFY-ROW-COUNT-MISMATCH", passed, json.dumps(result))


# ---------------------------------------------------------------------------
# Group 3: Notification Job (scenarios 14-19)
# ---------------------------------------------------------------------------

def _get_notification_queue_url() -> str:
    sqs = _aws_client("sqs")
    return sqs.get_queue_url(QueueName="nemoguard-notifications-queue")["QueueUrl"]


def scenario_14_poison_pill_first() -> ScenarioResult:
    rc, out = _run_break_script("break_notification_scenario.py", "poison_pill")
    ok = "KeyError" in out and "FunctionError: Unhandled" in out
    return ScenarioResult("NOTIF-POISON-PILL-FIRST", ok, "real KeyError observed" if ok else out[-300:])


def scenario_15_poison_pill_redelivery() -> ScenarioResult:
    rc1, out1 = _run_break_script("break_notification_scenario.py", "poison_pill")
    rc2, out2 = _run_break_script("break_notification_scenario.py", "poison_pill")
    ok = "KeyError" in out2 and "FunctionError: Unhandled" in out2
    return ScenarioResult("NOTIF-POISON-PILL-REDELIVERY", ok, "second poison_pill invocation also genuinely failed" if ok else out2[-300:])


def scenario_16_queue_backup_multi() -> ScenarioResult:
    for _ in range(3):
        _run_break_script("break_notification_scenario.py", "poison_pill")
    from src.domain.tools.aws_observability_tools import get_sqs_queue_attributes
    queue_url = _get_notification_queue_url()
    result = json.loads(get_sqs_queue_attributes(queue_url))
    count = int(result.get("attributes", {}).get("ApproximateNumberOfMessages", 0))
    passed = count >= 1
    return ScenarioResult("NOTIF-QUEUE-BACKUP-MULTI", passed, f"queue backlog after 3x poison_pill: {count} message(s) approx")


def scenario_17_notif_healthy() -> ScenarioResult:
    rc, out = _run_break_script("break_notification_scenario.py", "healthy")
    ok = "FunctionError" not in out and "Job succeeded" in out
    return ScenarioResult("NOTIF-HEALTHY-BASELINE", ok, "healthy notification succeeded" if ok else out[-300:])


def scenario_18_queue_inspect_only() -> ScenarioResult:
    from src.domain.tools.aws_observability_tools import peek_sqs_messages
    queue_url = _get_notification_queue_url()
    result = json.loads(peek_sqs_messages(queue_url, max_messages=10))
    passed = "error" not in result
    return ScenarioResult("NOTIF-QUEUE-INSPECT-ONLY", passed, json.dumps(result)[:300])


def scenario_19_quarantine_dry_run() -> ScenarioResult:
    from src.domain.tools.aws_observability_tools import quarantine_poison_messages
    _run_break_script("break_notification_scenario.py", "poison_pill")
    queue_url = _get_notification_queue_url()
    result = json.loads(quarantine_poison_messages(queue_url, "user_id", dry_run=True))
    passed = result.get("dry_run") is True and "quarantined_count" in result
    return ScenarioResult("NOTIF-QUARANTINE-DRY-RUN", passed, json.dumps(result)[:300])


# ---------------------------------------------------------------------------
# Group 4: Pipeline / Step Functions (scenarios 20-23)
# ---------------------------------------------------------------------------

def scenario_20_pipeline_ingest_fails() -> ScenarioResult:
    rc, out = _run_break_script("break_pipeline_scenario.py", "ingest_step_fails", timeout=45)
    ok = "execution_arn" in out and ("FAILED" in out or "Execution status: FAILED" in out)
    return ScenarioResult("PIPELINE-INGEST-STEP-FAILS", ok, out[-300:])


def scenario_21_pipeline_order_events_fails() -> ScenarioResult:
    rc, out = _run_break_script("break_pipeline_scenario.py", "order_events_step_fails", timeout=45)
    ok = "execution_arn" in out and ("FAILED" in out or "Execution status: FAILED" in out)
    return ScenarioResult("PIPELINE-ORDER-EVENTS-STEP-FAILS", ok, out[-300:])


def scenario_22_pipeline_healthy() -> ScenarioResult:
    rc, out = _run_break_script("break_pipeline_scenario.py", "healthy", timeout=45)
    ok = "execution_arn" in out and "SUCCEEDED" in out
    return ScenarioResult("PIPELINE-HEALTHY-BASELINE", ok, out[-300:])


def scenario_23_pipeline_execution_inspect() -> ScenarioResult:
    from src.domain.tools.aws_observability_tools import describe_step_function_execution
    rc, out = _run_break_script("break_pipeline_scenario.py", "ingest_step_fails", timeout=45)
    execution_arn = None
    for line in out.splitlines():
        if line.startswith("execution_arn = "):
            execution_arn = line.split("= ", 1)[1].strip()
    if not execution_arn:
        return ScenarioResult("PIPELINE-EXECUTION-INSPECT", False, "could not extract execution_arn from trigger output")
    result = json.loads(describe_step_function_execution(execution_arn))
    passed = "error" not in result and result.get("status") in ("FAILED", "SUCCEEDED", "RUNNING")
    return ScenarioResult("PIPELINE-EXECUTION-INSPECT", passed, json.dumps(result)[:300])


# ---------------------------------------------------------------------------
# Group 5: Alarm / Observability Lifecycle (scenarios 24-27)
# ---------------------------------------------------------------------------

def _reset_alarm(alarm_name: str) -> None:
    cw = _aws_client("cloudwatch")
    try:
        cw.set_alarm_state(AlarmName=alarm_name, StateValue="OK", StateReason="Reset by scenario catalog runner.")
        time.sleep(2)
    except Exception:
        pass


def scenario_24_alarm_trip_on_first_error() -> ScenarioResult:
    alarm_name = "nemoguard-ingest-job-errors"
    _reset_alarm(alarm_name)
    _run_break_script("break_scenario.py", "schema_drift")
    # Real CloudWatch alarm evaluation is genuinely asynchronous -- a
    # fixed short sleep was observed live to sometimes race the actual
    # evaluation cycle (a real environment-timing characteristic, not a
    # product bug). Poll with real re-checks rather than a single sleep.
    cw = _aws_client("cloudwatch")
    state = "UNKNOWN"
    # 30s was empirically too tight -- live runs showed the real
    # CloudWatch evaluation period + reporting delay can genuinely exceed
    # 30s (confirmed by re-checking alarm state manually immediately after
    # a "FAIL" and finding it HAD transitioned to ALARM, just slightly
    # later). 60s gives real headroom.
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        resp = cw.describe_alarms(AlarmNames=[alarm_name])
        alarms = resp.get("MetricAlarms", [])
        state = alarms[0]["StateValue"] if alarms else "UNKNOWN"
        if state == "ALARM":
            break
        time.sleep(2)
    passed = state == "ALARM"
    return ScenarioResult("ALARM-TRIP-ON-FIRST-ERROR", passed, f"alarm {alarm_name} state after real failure: {state}")


def _poll_for_alarm_state(alarm_name: str, target_state: str, timeout: int = 60) -> str:
    """Polls real CloudWatch alarm state until it reaches target_state or
    the timeout elapses, returning whatever the final observed state was.
    Real CloudWatch evaluation is genuinely asynchronous (see
    scenario_24's comment) -- a single fixed sleep was observed live to
    race the actual evaluation cycle here too."""
    from localstack_lab.remediate import check_alarm_state
    state = "UNKNOWN"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check_alarm_state(alarm_name)
        state = result.get("state", "UNKNOWN")
        if state == target_state:
            break
        time.sleep(2)
    return state


def scenario_25_alarm_no_renotify_on_repeat() -> ScenarioResult:
    alarm_name = "nemoguard-ingest-job-errors"
    _reset_alarm(alarm_name)
    _run_break_script("break_scenario.py", "oom_crash", timeout=90)
    state1 = _poll_for_alarm_state(alarm_name, "ALARM", timeout=60)
    # Second failure WITHOUT resetting -- CloudWatch should not re-notify
    # (state stays ALARM, no new OK->ALARM transition), which is the
    # real-world behavior this scenario documents. Since state1 is already
    # ALARM, this poll just needs to confirm it stayed there after a real
    # additional failure (not wait for a transition that shouldn't happen).
    _run_break_script("break_scenario.py", "db_outage")
    time.sleep(5)
    from localstack_lab.remediate import check_alarm_state
    state2 = check_alarm_state(alarm_name).get("state", "UNKNOWN")
    passed = state1 == "ALARM" and state2 == "ALARM"
    return ScenarioResult("ALARM-NO-RENOTIFY-ON-REPEAT", passed, f"state1={state1} state2={state2} (both ALARM, no reset in between, as expected)")


def scenario_26_alarm_acknowledge_after_fix() -> ScenarioResult:
    from src.domain.tools.aws_observability_tools import acknowledge_and_reset_alarm
    alarm_name = "nemoguard-order-events-job-errors"
    _run_break_script("break_order_events_scenario.py", "partial_write_crash")
    time.sleep(3)
    result = json.loads(acknowledge_and_reset_alarm(alarm_name, "Scenario catalog: acknowledging after verified test remediation."))
    passed = result.get("acknowledged") is True and result.get("state_after") == "OK"
    return ScenarioResult("ALARM-ACKNOWLEDGE-AFTER-FIX", passed, json.dumps(result))


def scenario_27_alarm_state_inspect_only() -> ScenarioResult:
    from localstack_lab.remediate import check_alarm_state
    result = check_alarm_state("nemoguard-ingest-job-errors")
    passed = "state" in result
    return ScenarioResult("ALARM-STATE-INSPECT-ONLY", passed, json.dumps(result))


# ---------------------------------------------------------------------------
# Group 6: Cross-cutting Alert Correlation (scenarios 28-30)
# ---------------------------------------------------------------------------

def _api_get(path: str, token: str, base: str = "http://localhost:8000") -> dict:
    import httpx
    r = httpx.get(f"{base}{path}", headers={"Authorization": f"Bearer {token}"}, timeout=15.0)
    r.raise_for_status()
    return r.json()


def _get_admin_token(base: str = "http://localhost:8000") -> str:
    import httpx
    r = httpx.get(f"{base}/api/v2/auth/mock-login?role=commander", timeout=10.0)
    r.raise_for_status()
    return r.json()["access_token"]


# Real multi-agent triage (Watcher -> Correlator -> RCA -> Impact -> Runbook
# -> Commander) was observed live to take up to 5-6 minutes end-to-end --
# matching WP-VAL-004's finding for the AI evaluation benchmark.
#
# CRITICAL correction discovered live during this harness's own development
# (per WP-VAL-002's exact same finding, re-confirmed here): success for a
# webhook-triggered alert is EITHER a genuinely new incident_id OR a real
# alert being correlated onto an EXISTING open incident that shares the
# same alarm -- the correlator CORRECTLY attaches a new alert to an
# already-open incident for the same alarm/job rather than creating a
# duplicate. This demo environment has real, already-open incidents from
# earlier sessions sharing these exact alarms, so a brand-new-ID-only check
# will ALWAYS produce a false "no incident observed" failure even though
# the alert was correctly ingested, correlated, and processed -- confirmed
# live by inspecting the audit trail of an existing incident (its
# alert count and audit_event rows genuinely grew during this exact test
# window). The functions below therefore treat EITHER a new incident_id OR
# alert-count growth on any pre-existing incident sharing that alarm as the
# real success signal, exactly matching run_validation_suite.py's (WP-VAL-002)
# already-correct pattern.
_INCIDENT_DETECTION_TIMEOUT = 180


def _snapshot_alert_counts(token: str) -> dict:
    """Returns {incident_id: alert_count} for every currently-open
    incident, used as a baseline to detect either a new incident OR
    alert-count growth on an existing one."""
    incidents = _api_get("/api/v2/incidents?state=all", token)
    return {i["incident_id"]: len(_api_get(f"/api/v2/incidents/{i['incident_id']}/alerts", token)) for i in incidents}


def _wait_for_new_alert(token: str, before_ids: set, before_counts: dict, timeout: int) -> Optional[str]:
    """Polls until either a genuinely new incident appears, or any
    pre-existing incident's alert count grows -- the real success signal
    for 'this alert was ingested and processed', per the design note
    above. Returns the affected incident_id, or None on timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        incidents = _api_get("/api/v2/incidents?state=all", token)
        new_ids = [i["incident_id"] for i in incidents if i["incident_id"] not in before_ids]
        if new_ids:
            return new_ids[0]
        for i in incidents:
            iid = i["incident_id"]
            if iid in before_counts:
                current = len(_api_get(f"/api/v2/incidents/{iid}/alerts", token))
                if current > before_counts[iid]:
                    return iid
        time.sleep(3)
    return None


def scenario_28_correlation_same_alarm() -> ScenarioResult:
    token = _get_admin_token()
    before_ids = {i["incident_id"] for i in _api_get("/api/v2/incidents?state=all", token)}
    before_counts = _snapshot_alert_counts(token)
    _reset_alarm("nemoguard-ingest-job-errors")
    _run_break_script("break_scenario.py", "schema_drift")

    incident_id = _wait_for_new_alert(token, before_ids, before_counts, _INCIDENT_DETECTION_TIMEOUT)
    if not incident_id:
        return ScenarioResult("CORRELATION-SAME-ALARM-NEW-INCIDENT", False, f"no new incident and no existing-incident alert growth observed within {_INCIDENT_DETECTION_TIMEOUT}s")

    before_count2 = len(_api_get(f"/api/v2/incidents/{incident_id}/alerts", token))
    _reset_alarm("nemoguard-ingest-job-errors")
    _run_break_script("break_scenario.py", "oom_crash", timeout=90)

    deadline2 = time.monotonic() + 90
    same_incident_confirmed = False
    while time.monotonic() < deadline2:
        after_count = len(_api_get(f"/api/v2/incidents/{incident_id}/alerts", token))
        if after_count > before_count2:
            same_incident_confirmed = True
            break
        time.sleep(3)

    return ScenarioResult(
        "CORRELATION-SAME-ALARM-NEW-INCIDENT", same_incident_confirmed,
        f"incident={incident_id} alert_count before={before_count2} after={'grew' if same_incident_confirmed else 'unchanged'}",
    )


def scenario_29_correlation_different_alarm() -> ScenarioResult:
    token = _get_admin_token()
    before_ids = {i["incident_id"] for i in _api_get("/api/v2/incidents?state=all", token)}
    before_counts = _snapshot_alert_counts(token)
    _reset_alarm("nemoguard-ingest-job-errors")
    _run_break_script("break_scenario.py", "schema_drift")
    ingest_incident_id = _wait_for_new_alert(token, before_ids, before_counts, _INCIDENT_DETECTION_TIMEOUT)
    if not ingest_incident_id:
        return ScenarioResult("CORRELATION-DIFFERENT-ALARM-NEW-INCIDENT", False, f"no ingest-side incident/alert-growth observed within {_INCIDENT_DETECTION_TIMEOUT}s")

    before_ids2 = {i["incident_id"] for i in _api_get("/api/v2/incidents?state=all", token)}
    before_counts2 = _snapshot_alert_counts(token)
    _reset_alarm("nemoguard-order-events-job-errors")
    _run_break_script("break_order_events_scenario.py", "partial_write_crash")
    order_events_incident_id = _wait_for_new_alert(token, before_ids2, before_counts2, _INCIDENT_DETECTION_TIMEOUT)

    passed = bool(order_events_incident_id)
    # The two REAL failure domains (ingest vs order_events) trip DIFFERENT
    # alarms and should therefore correlate to different incidents. This is
    # only a genuine anomaly if they landed on the exact SAME incident_id
    # despite being different alarms -- report that explicitly if observed,
    # rather than requiring a brand-new ID for the second one (which is not
    # actually the correctness criterion here).
    if passed and order_events_incident_id == ingest_incident_id:
        passed = False
    return ScenarioResult(
        "CORRELATION-DIFFERENT-ALARM-NEW-INCIDENT", passed,
        f"ingest_incident={ingest_incident_id} order_events_incident={order_events_incident_id} (must differ)",
    )


def scenario_30_correlation_alert_count_growth() -> ScenarioResult:
    token = _get_admin_token()
    before_ids = {i["incident_id"] for i in _api_get("/api/v2/incidents?state=all", token)}
    before_counts = _snapshot_alert_counts(token)
    _reset_alarm("nemoguard-ingest-job-errors")
    _run_break_script("break_scenario.py", "schema_drift")

    incident_id = _wait_for_new_alert(token, before_ids, before_counts, _INCIDENT_DETECTION_TIMEOUT)
    if not incident_id:
        return ScenarioResult("CORRELATION-ALERT-COUNT-GROWTH", False, f"no incident/alert-growth observed within {_INCIDENT_DETECTION_TIMEOUT}s")

    incident_before = next(i for i in _api_get("/api/v2/incidents?state=all", token) if i["incident_id"] == incident_id)
    status_before = incident_before["status"]
    alert_count_before = len(_api_get(f"/api/v2/incidents/{incident_id}/alerts", token))

    _reset_alarm("nemoguard-ingest-job-errors")
    _run_break_script("break_scenario.py", "db_outage")

    deadline2 = time.monotonic() + 90
    grew = False
    while time.monotonic() < deadline2:
        alert_count_after = len(_api_get(f"/api/v2/incidents/{incident_id}/alerts", token))
        if alert_count_after > alert_count_before:
            grew = True
            break
        time.sleep(3)

    incident_after = next(i for i in _api_get("/api/v2/incidents?state=all", token) if i["incident_id"] == incident_id)
    status_after = incident_after["status"]

    passed = grew  # status_before == status_after is EXPECTED (documenting that correlation alone doesn't change status), not asserted as pass/fail
    return ScenarioResult(
        "CORRELATION-ALERT-COUNT-GROWTH", passed,
        f"alert_count {alert_count_before}->grew={grew}; status {status_before}->{status_after} (status staying same on correlation is expected, real behavior)",
    )


ALL_SCENARIOS = [
    scenario_1_schema_drift,
    scenario_2_oom_crash,
    scenario_3_db_outage,
    scenario_4_missing_input_file,
    scenario_5_malformed_json,
    scenario_6_ingest_healthy,
    scenario_7_partial_write_small,
    scenario_8_partial_write_early,
    scenario_9_partial_write_late,
    scenario_10_duplicate_write,
    scenario_11_order_healthy,
    scenario_12_staleness_check,
    scenario_13_verify_row_count_mismatch,
    scenario_14_poison_pill_first,
    scenario_15_poison_pill_redelivery,
    scenario_16_queue_backup_multi,
    scenario_17_notif_healthy,
    scenario_18_queue_inspect_only,
    scenario_19_quarantine_dry_run,
    scenario_20_pipeline_ingest_fails,
    scenario_21_pipeline_order_events_fails,
    scenario_22_pipeline_healthy,
    scenario_23_pipeline_execution_inspect,
    scenario_24_alarm_trip_on_first_error,
    scenario_25_alarm_no_renotify_on_repeat,
    scenario_26_alarm_acknowledge_after_fix,
    scenario_27_alarm_state_inspect_only,
    scenario_28_correlation_same_alarm,
    scenario_29_correlation_different_alarm,
    scenario_30_correlation_alert_count_growth,
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full 30-scenario real-failure catalog live.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", default=None)
    parser.add_argument("--only", default=None, help="Comma-separated list of scenario function names to run (for debugging a subset).")
    args = parser.parse_args()

    scenarios_to_run = ALL_SCENARIOS
    if args.only:
        wanted = set(args.only.split(","))
        scenarios_to_run = [s for s in ALL_SCENARIOS if s.__name__ in wanted]

    results: list[ScenarioResult] = []
    for fn in scenarios_to_run:
        start = time.monotonic()
        if not args.json:
            print(f"Running {fn.__name__} ...", flush=True)
        try:
            result = fn()
        except Exception as e:
            result = ScenarioResult(fn.__name__, False, f"EXCEPTION: {e}")
        result.duration_seconds = round(time.monotonic() - start, 1)
        results.append(result)
        if not args.json:
            mark = "PASS" if result.passed else "FAIL"
            print(f"  [{mark}] {result.scenario_id}: {result.detail[:200]} ({result.duration_seconds}s)")

    passed_count = sum(1 for r in results if r.passed)
    total = len(results)

    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "results": [asdict(r) for r in results],
        "passed": passed_count,
        "total": total,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print()
        for r in results:
            mark = "PASS" if r.passed else "FAIL"
            print(f"{r.scenario_id:<40} {mark}")
        print(f"\n{passed_count}/{total} PASS")

    if args.out:
        with open(args.out, "w") as f:
            json.dump(summary, f, indent=2)
        if not args.json:
            print(f"\nWrote results to {args.out}")

    return 0 if passed_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
