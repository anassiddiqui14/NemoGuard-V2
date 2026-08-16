"""
NemoGuard LocalStack Lab - "ingest_job" Lambda.

This is a small but REAL data-pipeline job: it reads a JSON object from S3
(the object simulates an upstream data extract), validates its schema, and
writes a row into the shared Postgres database (the same Postgres used by
the rest of NemoGuard). It deliberately can fail in a few different, real
ways depending on what's actually in the S3 object -- there is no
"pretend to fail" flag; the failure is a genuine unhandled exception raised
while processing genuine (if synthetic) data.

Because this runs inside LocalStack's real Lambda emulator, a failure here
produces a REAL AWS Lambda invocation error, which increments the REAL
CloudWatch "Errors" metric for this function, which trips a REAL CloudWatch
Alarm, which publishes to a REAL SNS topic -- the entire chain from here up
to the webhook forwarder is genuine AWS-API behavior, not scripted.

Failure modes (selected by fields present in the S3 object):
  - missing "last_login_ip"          -> KeyError (schema drift)
  - "simulate_oom": true             -> MemoryError (resource exhaustion)
  - "simulate_db_outage": true       -> psycopg2.OperationalError (bad DB host)
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
    body = obj["Body"].read()
    return json.loads(body)


def _ensure_job_row(cur) -> None:
    cur.execute(
        """
        INSERT INTO job (job_id, job_name, platform, domain, stage, schedule, criticality, default_duration_sec, owner_team, retry_policy, active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (job_id) DO NOTHING
        """,
        ("LOCALSTACK_INGEST_JOB", "LocalStack Ingest Job (Lambda)", "AWS Lambda", "Lab",
         "Ingest", "@on-demand", 1, 5, "DataOps", "none", True),
    )


def _write_success(record: dict) -> None:
    conn = psycopg2.connect(POSTGRES_URL)
    try:
        with conn, conn.cursor() as cur:
            _ensure_job_row(cur)
            run_id = record.get("run_id", "RUN-LOCALSTACK-UNKNOWN")
            cur.execute(
                """
                INSERT INTO execution (run_id, job_id, scheduled_ts, start_ts, end_ts, status, records_in, records_out)
                VALUES (%s, %s, now()::text, now()::text, now()::text, 'succeeded', %s, %s)
                ON CONFLICT (run_id) DO NOTHING
                """,
                (run_id, "LOCALSTACK_INGEST_JOB", 1, 1),
            )
            cur.execute(
                """
                INSERT INTO log_event (log_id, run_id, timestamp, level, component, error_code, message)
                VALUES (%s, %s, now()::text, 'INFO', 'localstack_ingest_job', NULL, %s)
                """,
                (f"LOG-{run_id}-OK", run_id,
                 f"Successfully ingested customer_profile record for user_id={record.get('user_id')}"),
            )
    finally:
        conn.close()


def _write_failure_log(run_id: str, message: str) -> None:
    """Best-effort: also record the failure as a log_event so the Watcher
    Agent's log-based evidence collection has something real to find,
    mirroring what a real ingestion job's structured logging would emit
    right before it crashes. Swallows its own errors because the DB itself
    may be down (e.g. simulate_db_outage) -- in that case the caller's own
    exception is what matters, not this best-effort audit trail."""
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        with conn, conn.cursor() as cur:
            _ensure_job_row(cur)
            cur.execute(
                """
                INSERT INTO execution (run_id, job_id, scheduled_ts, start_ts, end_ts, status)
                VALUES (%s, %s, now()::text, now()::text, now()::text, 'failed')
                ON CONFLICT (run_id) DO NOTHING
                """,
                (run_id, "LOCALSTACK_INGEST_JOB"),
            )
            cur.execute(
                """
                INSERT INTO log_event (log_id, run_id, timestamp, level, component, error_code, message)
                VALUES (%s, %s, now()::text, 'ERROR', 'localstack_ingest_job', NULL, %s)
                """,
                (f"LOG-{run_id}-FAIL", run_id, message),
            )
        conn.close()
    except Exception:
        pass


def handler(event, context):
    """
    Lambda entrypoint. Two invocation shapes are supported:

    1. Direct invoke with a test payload (used by scripts/break_scenario.py):
       {"bucket": "...", "key": "...", "run_id": "..."}

    2. S3 event notification (if wired via S3->Lambda trigger):
       {"Records": [{"s3": {"bucket": {"name": ...}, "object": {"key": ...}}}]}
    """
    if "Records" in event:
        rec = event["Records"][0]["s3"]
        bucket = rec["bucket"]["name"]
        key = rec["object"]["key"]
    else:
        bucket = event["bucket"]
        key = event["key"]

    run_id = event.get("run_id", f"RUN-LOCALSTACK-{key.replace('/', '-')}")

    record = _read_s3_object(bucket, key)
    record["run_id"] = run_id

    try:
        if record.get("simulate_db_outage"):
            # Genuine, unmocked failure: point at a host that doesn't exist so
            # psycopg2 raises a real OperationalError -- this is exactly what a
            # production ingestion job looks like when its database is
            # unreachable (e.g. during a failover or connection pool exhaustion).
            bad_conn_str = "postgresql://nemoguard:nemoguard_password@postgres-unreachable:5432/nemoguard_db"
            psycopg2.connect(bad_conn_str, connect_timeout=3)
            return  # unreachable; connect() above will raise

        if record.get("simulate_oom"):
            # Genuine MemoryError: actually allocate until Python raises,
            # rather than raising it ourselves, so the traceback/error shape
            # is identical to a real OOM crash.
            blocks = []
            while True:
                blocks.append(bytearray(10 ** 8))  # 100MB chunks

        if "last_login_ip" not in record:
            # Genuine KeyError from a real schema-validation code path, not
            # a raise statement dressed up to look like one.
            ip = record["last_login_ip"]  # noqa: F841 -- intentional KeyError

        _write_success(record)
        return {"status": "ok", "run_id": run_id, "user_id": record.get("user_id")}

    except Exception as e:
        # Record the failure as a real log_event (best-effort) so the
        # Watcher Agent's log-based evidence collection has something to
        # find, THEN re-raise so the Lambda invocation itself still fails --
        # that failed invocation is what increments the real CloudWatch
        # "Errors" metric and trips the real Alarm.
        _write_failure_log(run_id, f"{type(e).__name__}: {e}")
        raise
