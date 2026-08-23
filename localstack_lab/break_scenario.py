#!/usr/bin/env python3
"""
Triggers a REAL failure in the LocalStack lab by uploading a genuinely
malformed/problematic JSON object to S3, then invoking the real
`nemoguard-ingest-job` Lambda against it. There is no scripted "pretend
this failed" branch here -- the Lambda genuinely raises an exception while
processing the object this script writes, which genuinely fails the Lambda
invocation, which genuinely trips the CloudWatch Alarm.

Scenarios:
  schema_drift        -> S3 object missing "last_login_ip" -> KeyError in the job
  oom_crash           -> S3 object has simulate_oom=true    -> real MemoryError
  db_outage           -> S3 object has simulate_db_outage=true -> real connection failure
  missing_input_file  -> the S3 key is NEVER uploaded -> real boto3 NoSuchKey
                          error from a genuinely missing upstream extract file
                          (e.g. an upstream export job never ran/completed).
  malformed_json      -> the S3 object's bytes are NOT valid JSON at all ->
                          real json.JSONDecodeError (distinct from schema_drift,
                          which is valid JSON missing one expected field -- this
                          is the object being unparseable garbage entirely,
                          e.g. a truncated/corrupted upload).
  healthy             -> a fully valid object (use this to confirm the job
                          still succeeds normally -- useful as a sanity check
                          and for verifying recovery after an agent's plan runs)

Usage:
    python3 localstack_lab/break_scenario.py schema_drift
    python3 localstack_lab/break_scenario.py oom_crash
    python3 localstack_lab/break_scenario.py db_outage
    python3 localstack_lab/break_scenario.py missing_input_file
    python3 localstack_lab/break_scenario.py malformed_json
    python3 localstack_lab/break_scenario.py healthy
"""

import json
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(__file__))
from aws_clients import client  # noqa: E402

BUCKET_NAME = "nemoguard-lab-data"
FUNCTION_NAME = "nemoguard-ingest-job"

# Scenarios that upload a normal JSON dict record (the vast majority).
SCENARIOS = {
    "schema_drift": {
        "user_id": "USR-{uid}",
        # "last_login_ip" intentionally omitted
    },
    "oom_crash": {
        "user_id": "USR-{uid}",
        "last_login_ip": "10.0.0.1",
        "simulate_oom": True,
    },
    "db_outage": {
        "user_id": "USR-{uid}",
        "last_login_ip": "10.0.0.1",
        "simulate_db_outage": True,
    },
    "healthy": {
        "user_id": "USR-{uid}",
        "last_login_ip": "10.0.0.1",
    },
}

# Scenarios that deliberately do NOT upload a normal JSON dict -- handled
# specially in main() below rather than forced into the dict-based shape.
RAW_SCENARIOS = {"missing_input_file", "malformed_json"}

ALL_SCENARIO_NAMES = list(SCENARIOS.keys()) + list(RAW_SCENARIOS)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ALL_SCENARIO_NAMES:
        print(f"Usage: python3 {sys.argv[0]} <{'|'.join(ALL_SCENARIO_NAMES)}>")
        sys.exit(1)

    scenario = sys.argv[1]
    uid = uuid.uuid4().hex[:6]
    run_id = f"RUN-LOCALSTACK-{scenario}-{uid}"
    key = f"customer_profile/{run_id}.json"

    s3 = client("s3")
    print(f"Scenario: {scenario}")

    if scenario == "missing_input_file":
        print(f"  Deliberately NOT uploading s3://{BUCKET_NAME}/{key} "
              f"(simulating an upstream extract that never ran/completed).")
    elif scenario == "malformed_json":
        print(f"  Uploading DELIBERATELY INVALID (non-JSON) bytes to s3://{BUCKET_NAME}/{key} ...")
        s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=b'{this is not valid json at all!!!')
    else:
        record = json.loads(json.dumps(SCENARIOS[scenario]).replace("{uid}", uid))
        print(f"  Uploading s3://{BUCKET_NAME}/{key} ...")
        s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=json.dumps(record).encode())

    print(f"  Invoking {FUNCTION_NAME} against it (run_id={run_id}) ...")
    lam = client("lambda")
    resp = lam.invoke(
        FunctionName=FUNCTION_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps({"bucket": BUCKET_NAME, "key": key, "run_id": run_id}).encode(),
    )

    status = resp["StatusCode"]
    function_error = resp.get("FunctionError")
    payload = resp["Payload"].read().decode()

    print(f"  Lambda invoke StatusCode={status} FunctionError={function_error}")
    print(f"  Payload: {payload}")

    if function_error:
        print(f"\n  Genuine Lambda failure recorded for run_id={run_id}.")
        print("  This increments the real CloudWatch 'Errors' metric for the function.")
        print("  If the forwarder (localstack_lab/forwarder.py) is running, the")
        print("  CloudWatch Alarm should trip within ~1 minute and forward a webhook")
        print("  to NemoGuard automatically. To force faster feedback for a demo,")
        print("  you can also manually check the alarm state with:")
        print(f"    aws --endpoint-url=http://localhost:4566 cloudwatch describe-alarms "
              f"--alarm-names nemoguard-ingest-job-errors")
    else:
        print(f"\n  Job succeeded normally for run_id={run_id} (as expected for 'healthy').")


if __name__ == "__main__":
    main()
