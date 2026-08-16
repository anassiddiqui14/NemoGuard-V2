"""
Real remediation + verification actions against the LocalStack lab, used by
src/tools/write_tools.py so that when an agent's recovery plan says "rerun
the job" or "fix the schema," something ACTUALLY happens against a real
(if local) AWS Lambda + Postgres -- and verification checks REAL state
afterward instead of hardcoding success.

This module is intentionally decoupled from write_tools.py's import graph:
write_tools.py imports these functions lazily (only when
NEMOGUARD_LOCALSTACK_LAB=1 is set) so that normal NemoGuard operation
(against real cloud infra, or with the lab not running) is completely
unaffected if boto3/LocalStack aren't available.
"""

import json
import os

import psycopg2

from .aws_clients import client

BUCKET_NAME = "nemoguard-lab-data"
FUNCTION_NAME = "nemoguard-ingest-job"

POSTGRES_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db",
)


def rerun_ingest_job(run_id: str) -> dict:
    """Re-invokes the real Lambda with a corrected ("healthy") payload for
    the given run_id, simulating an agent's "rerun the job after fixing the
    schema" remediation step. Returns the real Lambda invocation result."""
    key = f"customer_profile/{run_id}-remediated.json"
    record = {"user_id": run_id, "last_login_ip": "10.0.0.1"}

    s3 = client("s3")
    s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=json.dumps(record).encode())

    lam = client("lambda")
    resp = lam.invoke(
        FunctionName=FUNCTION_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps({"bucket": BUCKET_NAME, "key": key, "run_id": run_id}).encode(),
    )
    payload = json.loads(resp["Payload"].read().decode())
    function_error = resp.get("FunctionError")

    return {
        "success": function_error is None,
        "function_error": function_error,
        "payload": payload,
    }


def check_job_succeeded(run_id: str) -> dict:
    """REAL verification: queries the actual `execution` table in Postgres
    (written by the real Lambda) to check whether this run_id now has a
    'succeeded' status row -- replacing the previous hardcoded
    `resolved: True` in write_tools.verify_incident_recovery."""
    conn = psycopg2.connect(POSTGRES_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM execution WHERE run_id = %s ORDER BY end_ts DESC LIMIT 1",
                (run_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"resolved": False, "reason": f"No execution row found for run_id={run_id}"}
            status = row[0]
            return {
                "resolved": status == "succeeded",
                "status": status,
                "reason": f"execution.status = '{status}' for run_id={run_id}",
            }
    finally:
        conn.close()


def check_alarm_state(alarm_name: str = "nemoguard-ingest-job-errors") -> dict:
    """REAL verification: queries the actual CloudWatch alarm state."""
    cw = client("cloudwatch")
    resp = cw.describe_alarms(AlarmNames=[alarm_name])
    alarms = resp.get("MetricAlarms", [])
    if not alarms:
        return {"state": "UNKNOWN", "reason": f"Alarm {alarm_name} not found"}
    state = alarms[0]["StateValue"]
    return {"state": state, "resolved": state == "OK", "reason": f"CloudWatch alarm state = {state}"}


ORDER_EVENTS_FUNCTION_NAME = "nemoguard-order-events-job"


def idempotent_rerun_order_events_job(run_id: str, orders: list) -> dict:
    """Safe, idempotent rerun for the order_events write-job: checks for a
    stale/partial write from a previous attempt FIRST, cleans it up if
    found (real DELETE scoped to run_id, not a broader wipe), re-invokes
    the real Lambda with the corrected/full batch, and then verifies the
    resulting row count actually matches what was expected -- this is
    the concrete implementation of the "staleness check -> cleanup ->
    rerun -> verify" policy the agents are instructed to follow, exposed
    as a single safe action so execute_simulated_action can call it
    atomically instead of the agent orchestrating each raw tool call
    itself during execution.
    """
    from src.domain.tools.aws_observability_tools import (
        check_table_staleness, cleanup_partial_write, verify_row_count_matches_expected,
    )
    import json as _json

    steps_log = []

    staleness = _json.loads(check_table_staleness("order_events", run_id, expected_row_count=len(orders)))
    steps_log.append({"step": "check_table_staleness", "result": staleness})

    if staleness.get("is_stale_or_partial"):
        cleanup_dry = _json.loads(cleanup_partial_write("order_events", run_id, dry_run=True))
        steps_log.append({"step": "cleanup_partial_write(dry_run=True)", "result": cleanup_dry})

        cleanup_real = _json.loads(cleanup_partial_write("order_events", run_id, dry_run=False))
        steps_log.append({"step": "cleanup_partial_write(dry_run=False)", "result": cleanup_real})

    # Real rerun: upload the (corrected/full) batch and invoke the real Lambda.
    key = f"order_events/{run_id}-rerun.json"
    s3 = client("s3")
    s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=_json.dumps({"orders": orders}).encode())

    lam = client("lambda")
    resp = lam.invoke(
        FunctionName=ORDER_EVENTS_FUNCTION_NAME,
        InvocationType="RequestResponse",
        Payload=_json.dumps({"bucket": BUCKET_NAME, "key": key, "run_id": run_id}).encode(),
    )
    payload = _json.loads(resp["Payload"].read().decode())
    function_error = resp.get("FunctionError")
    steps_log.append({"step": "rerun_lambda", "function_error": function_error, "payload": payload})

    verification = _json.loads(verify_row_count_matches_expected("order_events", run_id, expected_row_count=len(orders)))
    steps_log.append({"step": "verify_row_count_matches_expected", "result": verification})

    return {
        "success": function_error is None and verification.get("verified", False),
        "run_id": run_id,
        "steps": steps_log,
    }
