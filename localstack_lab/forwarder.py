#!/usr/bin/env python3
"""
Polls the `nemoguard-lab-alerts-queue` SQS queue (subscribed to the real
CloudWatch Alarm -> SNS topic set up by provision.py) and forwards each
notification into NemoGuard's existing webhook ingestion endpoint
(/api/v2/ingest/webhook) -- the SAME endpoint the synthetic simulator and
the real-alert-replay script already use, so no changes are needed on the
NemoGuard side to consume "real" LocalStack-sourced incidents.

This is the one piece of genuinely custom "glue" code in the lab: real AWS
doesn't speak your webhook's exact JSON shape, so *some* translation layer
is always required in a real deployment too (this is exactly what a
CloudWatch->SNS->Lambda subscriber would do in production). Everything
upstream of this point (the Lambda failing, the Errors metric incrementing,
the Alarm transitioning to ALARM, the SNS/SQS delivery) is unmodified,
genuine AWS-API behavior running against LocalStack.

Usage:
    python3 localstack_lab/forwarder.py
    (Ctrl+C to stop; safe to leave running in a terminal throughout testing)
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import httpx
import psycopg2

sys.path.insert(0, os.path.dirname(__file__))
from aws_clients import client  # noqa: E402

QUEUE_NAME = "nemoguard-lab-alerts-queue"
NEMOGUARD_API_BASE = os.environ.get("NEMOGUARD_API_BASE", "http://localhost:8000")
POLL_INTERVAL_SEC = float(os.environ.get("FORWARDER_POLL_INTERVAL_SEC", "3"))
POSTGRES_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://nemoguard:nemoguard_password@localhost:5432/nemoguard_db",
)


def _severity_from_alarm_state(alarm_body: dict) -> str:
    # CloudWatch alarm-to-ALARM transitions are, by construction, things we
    # care about; map straightforwardly to "critical" for a hard Lambda
    # error-rate breach.
    return "critical"


# Real CloudWatch alarm Dimensions carry the AWS resource name (Lambda
# function name), not NemoGuard's own job_id -- this mapping is the one
# place that translates between the two. Previously this forwarder always
# called _most_recent_failed_run_id() with its hardcoded default
# (LOCALSTACK_INGEST_JOB) regardless of which function's alarm actually
# fired, so every incident sourced from nemoguard-order-events-job (or any
# other lab job) got a genuinely wrong run_id, silently starving the RCA
# agent of the real logs for the failure that was actually reported.
FUNCTION_NAME_TO_JOB_ID = {
    "nemoguard-ingest-job": "LOCALSTACK_INGEST_JOB",
    "nemoguard-order-events-job": "LOCALSTACK_ORDER_EVENTS_JOB",
    "nemoguard-notification-job": "LOCALSTACK_NOTIFICATION_JOB",
}


def _most_recent_failed_run_id(job_id: str = "LOCALSTACK_INGEST_JOB") -> str | None:
    """Looks up the most recent 'failed' execution row for this job.

    CloudWatch Alarms only carry an aggregate metric breach (e.g. "Errors
    Sum >= 1"), not the run_id of the specific invocation that failed --
    that identifier only exists in the Lambda's own application logs
    (written to log_event/execution by handler.py). Without this lookup,
    the forwarder was fabricating a brand-new run_id per alarm notification
    that had zero connection to any real log_event/execution row, which
    made the RCA Agent correctly-but-uselessly report "no logs found" for
    every LocalStack-sourced incident -- the agent's reasoning was fine,
    the underlying alert payload was just pointing at data that didn't
    exist. Looking up the real failing run_id here connects the incident
    to the actual logs the Lambda wrote.
    """
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT run_id FROM execution WHERE job_id = %s AND status = 'failed' "
                "ORDER BY end_ts DESC LIMIT 1",
                (job_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None
    except Exception as e:
        print(f"  !! could not look up real run_id from Postgres: {e}")
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def cloudwatch_alarm_to_webhook_payload(alarm_body: dict) -> dict:
    """Translates a real CloudWatch Alarm SNS notification body into the
    JSON shape NemoGuard's /api/v2/ingest/webhook already understands
    (same shape as simulator_backend/main.py's synthetic webhooks)."""
    function_name = None
    for dim in alarm_body.get("Trigger", {}).get("Dimensions", []):
        if dim.get("name") == "FunctionName":
            function_name = dim.get("value")

    job_id = FUNCTION_NAME_TO_JOB_ID.get(function_name, "LOCALSTACK_INGEST_JOB")
    real_run_id = _most_recent_failed_run_id(job_id)
    run_id = real_run_id or f"RUN-LOCALSTACK-{int(time.time())}"
    if not real_run_id:
        print("  !! WARNING: no matching failed execution row found; "
              "falling back to a synthetic run_id (RCA will have no logs to cite).")

    return {
        "source": "CloudWatch (LocalStack)",
        "type": "Alarm",
        "monitor_name": alarm_body.get("AlarmName", "Unknown Alarm"),
        "message": alarm_body.get(
            "NewStateReason",
            f"CloudWatch alarm {alarm_body.get('AlarmName')} entered ALARM state.",
        ),
        "tags": [
            f"service:{function_name or 'nemoguard-ingest-job'}",
            "env:localstack-lab",
            "severity:critical",
        ],
        "run_id": run_id,
        "alarm_name": alarm_body.get("AlarmName"),
        "new_state": alarm_body.get("NewStateValue"),
        "region": alarm_body.get("Region"),
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    sqs = client("sqs")
    queue_url = sqs.get_queue_url(QueueName=QUEUE_NAME)["QueueUrl"]

    print(f"Forwarder started. Polling {QUEUE_NAME} every {POLL_INTERVAL_SEC}s.")
    print(f"Forwarding to {NEMOGUARD_API_BASE}/api/v2/ingest/webhook\n")

    with httpx.Client(timeout=30) as http:
        while True:
            resp = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=int(min(POLL_INTERVAL_SEC, 20)),
            )
            messages = resp.get("Messages", [])

            for msg in messages:
                try:
                    # SNS wraps the actual alarm JSON inside an outer
                    # envelope's "Message" field.
                    sns_envelope = json.loads(msg["Body"])
                    alarm_body = json.loads(sns_envelope.get("Message", "{}"))

                    payload = cloudwatch_alarm_to_webhook_payload(alarm_body)
                    r = http.post(f"{NEMOGUARD_API_BASE}/api/v2/ingest/webhook", json=payload)
                    print(f"  -> forwarded alarm '{payload['alarm_name']}' "
                          f"(state={payload['new_state']}): HTTP {r.status_code}")

                except Exception as e:
                    print(f"  !! failed to process message: {e}")

                finally:
                    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"])

            if not messages:
                time.sleep(max(0, POLL_INTERVAL_SEC - 20))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nForwarder stopped.")
