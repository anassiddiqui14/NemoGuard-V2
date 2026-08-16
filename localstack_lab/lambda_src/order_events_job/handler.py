"""
NemoGuard LocalStack Lab - "order_events_job" Lambda.

Simulates a Glue-style ETL job that reads a batch of order events from S3
and writes them into a real Postgres table (`order_events`) row-by-row in
separate transactions -- deliberately NOT one atomic all-or-nothing
transaction, matching how many real Spark/Glue JDBC sinks actually behave
(batched commits, not a single wrapping transaction across the whole
write). This means a genuine mid-batch crash leaves the table in a real
partial-write state: some rows for this run_id committed, others missing.

This is the scenario an agent needs real tooling to handle correctly:
  1. Detect that a previous run left partial/stale data (row count for
     this run_id < expected_row_count from the manifest).
  2. Clean up (delete) the partial rows for that run_id before retrying --
     otherwise a naive rerun would double-write the rows that DID commit.
  3. Only then is it safe to rerun the job.

Failure modes (selected by fields in the S3 batch object):
  "simulate_partial_write_crash": true
      -> writes some rows successfully, then genuinely crashes
         (raises an exception) partway through the batch, leaving
         partial data in order_events for this run_id.
  (no special field) -> writes the full batch successfully.
"""

import json
import os

import boto3
import psycopg2

POSTGRES_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db",
)


def _read_s3_object(bucket: str, key: str) -> dict:
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ.get("LOCALSTACK_ENDPOINT", "http://localstack:4566"),
    )
    obj = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read())


def _ensure_job_row(cur) -> None:
    cur.execute(
        """
        INSERT INTO job (job_id, job_name, platform, domain, stage, schedule, criticality, default_duration_sec, owner_team, retry_policy, active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (job_id) DO NOTHING
        """,
        ("LOCALSTACK_ORDER_EVENTS_JOB", "LocalStack Order Events Job (Glue-style)", "AWS Glue (simulated)",
         "Lab", "Transform", "@on-demand", 1, 15, "DataOps", "none", True),
    )


def _write_manifest(conn, run_id: str, expected_row_count: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO order_events_run_manifest (run_id, expected_row_count) "
            "VALUES (%s, %s) ON CONFLICT (run_id) DO NOTHING",
            (run_id, expected_row_count),
        )
    conn.commit()


def _write_row_committed(conn, run_id: str, order: dict) -> None:
    """Writes ONE row in its OWN transaction (commits immediately) -- this
    is what makes a mid-batch crash a genuine partial-write, not something
    that automatically rolls back."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO order_events (run_id, order_id, event_type, amount) VALUES (%s, %s, %s, %s)",
            (run_id, order["order_id"], order["event_type"], order.get("amount")),
        )
    conn.commit()


def _log_execution(conn, run_id: str, status: str, message: str = None) -> None:
    with conn.cursor() as cur:
        _ensure_job_row(cur)
        cur.execute(
            """
            INSERT INTO execution (run_id, job_id, scheduled_ts, start_ts, end_ts, status)
            VALUES (%s, %s, now()::text, now()::text, now()::text, %s)
            ON CONFLICT (run_id) DO UPDATE SET status = EXCLUDED.status, end_ts = now()::text
            """,
            (run_id, "LOCALSTACK_ORDER_EVENTS_JOB", status),
        )
        if message:
            cur.execute(
                """
                INSERT INTO log_event (log_id, run_id, timestamp, level, component, error_code, message)
                VALUES (%s, %s, now()::text, %s, 'localstack_order_events_job', NULL, %s)
                """,
                (f"LOG-{run_id}-{status}", run_id, "ERROR" if status == "failed" else "INFO", message),
            )
    conn.commit()


def handler(event, context):
    if "Records" in event:
        rec = event["Records"][0]["s3"]
        bucket = rec["bucket"]["name"]
        key = rec["object"]["key"]
    else:
        bucket = event["bucket"]
        key = event["key"]

    run_id = event.get("run_id", f"RUN-LOCALSTACK-{key.replace('/', '-')}")

    batch = _read_s3_object(bucket, key)
    orders = batch.get("orders", [])
    simulate_crash = bool(batch.get("simulate_partial_write_crash"))
    crash_after_n = int(batch.get("crash_after_n_rows", max(1, len(orders) // 2)))

    conn = psycopg2.connect(POSTGRES_URL)
    try:
        _write_manifest(conn, run_id, expected_row_count=len(orders))

        written = 0
        for i, order in enumerate(orders):
            if simulate_crash and i == crash_after_n:
                # Genuine crash: rows [0, crash_after_n) are already
                # committed (each in its own transaction above); this
                # raise happens mid-batch, before the remaining rows are
                # written, leaving REAL partial data in order_events.
                _log_execution(
                    conn, run_id, "failed",
                    f"Job crashed after writing {written}/{len(orders)} rows "
                    f"(expected {len(orders)}). Partial data exists for run_id={run_id}.",
                )
                raise RuntimeError(
                    f"Simulated mid-batch crash: wrote {written}/{len(orders)} rows before failure."
                )
            _write_row_committed(conn, run_id, order)
            written += 1

        _log_execution(conn, run_id, "succeeded", f"Wrote {written}/{len(orders)} rows successfully.")
        return {"status": "ok", "run_id": run_id, "rows_written": written, "expected": len(orders)}
    finally:
        conn.close()
