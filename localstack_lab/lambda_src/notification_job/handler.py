"""
NemoGuard LocalStack Lab - "notification_job" Lambda.

Simulates a REAL SQS-consumer worker (e.g. a payment-notification
dispatcher) that polls `nemoguard-notifications-queue` and, for each
message, looks up the target user in Postgres and writes a delivery
receipt row. This is a genuinely different failure shape from the other
two lab jobs (S3->Lambda batch jobs): it's message-driven, and its
characteristic failure mode is a REAL "poison pill" -- one malformed
message that the consumer cannot process, which (without a redrive/DLQ
strategy) gets redelivered and crashes the consumer every time it's
picked up, effectively backing up the whole queue for every OTHER,
perfectly valid, message behind it.

This directly exercises capabilities that were registered in the tool
schema (`get_sqs_queue_attributes`, `peek_sqs_messages`) but had no real
lab scenario to actually produce a failure through -- until now.

Failure modes (selected by fields in the SQS message body):
  "simulate_poison_pill": true
      -> message is missing a required field ("user_id"), the handler
         raises a genuine KeyError while processing it. Because this
         Lambda is invoked directly against a single message (see
         break_notification_scenario.py) rather than via a real SQS
         event-source-mapping, the message is deliberately NOT deleted
         from the queue on failure -- exactly mirroring what a real SQS
         trigger does when a Lambda invocation fails (the message
         becomes visible again after the visibility timeout and will be
         redelivered), so the queue backs up for real, observably, via
         get_sqs_queue_attributes.
  (no special field) -> processes normally and writes a delivery receipt.
"""

import json
import os

import boto3
import psycopg2

POSTGRES_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db",
)
LOCALSTACK_ENDPOINT = os.environ.get("LOCALSTACK_ENDPOINT", "http://localstack:4566")


def _ensure_job_row(cur) -> None:
    cur.execute(
        """
        INSERT INTO job (job_id, job_name, platform, domain, stage, schedule, criticality, default_duration_sec, owner_team, retry_policy, active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (job_id) DO NOTHING
        """,
        ("LOCALSTACK_NOTIFICATION_JOB", "LocalStack Notification Job (SQS consumer)", "AWS Lambda (SQS-triggered, simulated)",
         "Lab", "Serve", "@continuous", 1, 5, "Platform", "sqs_redrive", True),
    )


def _log_execution(conn, run_id: str, status: str, message: str = None) -> None:
    with conn.cursor() as cur:
        _ensure_job_row(cur)
        cur.execute(
            """
            INSERT INTO execution (run_id, job_id, scheduled_ts, start_ts, end_ts, status)
            VALUES (%s, %s, now()::text, now()::text, now()::text, %s)
            ON CONFLICT (run_id) DO UPDATE SET status = EXCLUDED.status, end_ts = now()::text
            """,
            (run_id, "LOCALSTACK_NOTIFICATION_JOB", status),
        )
        if message:
            cur.execute(
                """
                INSERT INTO log_event (log_id, run_id, timestamp, level, component, error_code, message)
                VALUES (%s, %s, now()::text, %s, 'localstack_notification_job', NULL, %s)
                """,
                (f"LOG-{run_id}-{status}-{os.urandom(3).hex()}", run_id, "ERROR" if status == "failed" else "INFO", message),
            )
    conn.commit()


def handler(event, context):
    """Processes ONE SQS message body (passed directly by
    break_notification_scenario.py, simulating a single delivery
    attempt of a real SQS-triggered Lambda)."""
    run_id = event.get("run_id", "RUN-LOCALSTACK-notification-job")
    body = event.get("message_body", {})

    conn = psycopg2.connect(POSTGRES_URL)
    try:
        if body.get("simulate_poison_pill"):
            # Genuine failure: required field missing -> real KeyError.
            # We deliberately access it via [] (not .get()) so this is a
            # real unhandled exception, not a scripted "pretend to fail".
            user_id = body["user_id"]  # noqa: F841 -- intentionally raises if absent
            raise RuntimeError("unreachable")  # pragma: no cover
        user_id = body["user_id"]
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO log_event (log_id, run_id, timestamp, level, component, error_code, message) "
                "VALUES (%s, %s, now()::text, 'INFO', 'localstack_notification_job', NULL, %s)",
                (f"LOG-{run_id}-delivered-{os.urandom(3).hex()}", run_id, f"Notification delivered to {user_id}."),
            )
        conn.commit()
        _log_execution(conn, run_id, "succeeded", f"Delivered notification to {user_id}.")
        return {"status": "ok", "run_id": run_id, "user_id": user_id}
    except KeyError as e:
        _log_execution(
            conn, run_id, "failed",
            f"Poison-pill message: missing required field {e}. Message body: {json.dumps(body)}",
        )
        raise
    finally:
        conn.close()
