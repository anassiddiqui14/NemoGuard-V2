#!/usr/bin/env python3
"""
Triggers a REAL Step Functions execution of the multi-step
`nemoguard-daily-pipeline` state machine (IngestCustomerProfile ->
ProcessOrderEvents), so an agent can be tested against an incident whose
root cause lives in a SPECIFIC STATE of an orchestrated pipeline rather
than a single standalone Lambda -- exactly what
`describe_step_function_execution` is built to diagnose.

Scenarios:
  ingest_step_fails        -> the first state (ingest) fails with a real
                               schema-drift error (missing
                               "last_login_ip"), so the execution stops
                               there and ProcessOrderEvents never runs.
  order_events_step_fails  -> the ingest step succeeds, but the second
                               state (order events) genuinely crashes
                               mid-batch (partial write).
  healthy                  -> both steps succeed -- use to confirm
                               recovery after a fix.

This requires the `nemoguard-daily-pipeline` state machine to already
exist (created by provision.py's ensure_state_machine step).

Note on LocalStack Step Functions Lambda invocation:
LocalStack executes each Task state by directly invoking the referenced
Lambda ARN, so the two upstream Lambdas' real success/failure logic runs
exactly as it does when invoked standalone by break_scenario.py /
break_order_events_scenario.py -- the only difference here is the
ORCHESTRATION layer wrapping them, which is what makes this a genuinely
new incident shape to diagnose.

Usage:
    python3 localstack_lab/break_pipeline_scenario.py ingest_step_fails
    python3 localstack_lab/break_pipeline_scenario.py order_events_step_fails
    python3 localstack_lab/break_pipeline_scenario.py healthy
"""

import json
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(__file__))
from aws_clients import client  # noqa: E402

STATE_MACHINE_NAME = "nemoguard-daily-pipeline"
BUCKET_NAME = "nemoguard-lab-data"

# The ingest_job Lambda's handler expects {"bucket": ..., "key": ...}
# (see localstack_lab/lambda_src/ingest_job/handler.py); the order_events
# Lambda expects the same shape. Step Functions passes each Task's
# input as-is to the Lambda, so for this two-step chain we craft the
# INITIAL execution input to satisfy the ingest step, and separately
# stage the S3 object the order_events step will need if we want its own
# real scenario to trigger (its input is threaded through from the
# ingest step's return value in a real pipeline; for this lab exercise we
# keep the two steps loosely coupled and stage both S3 objects up front
# so either step's real failure path can be exercised independently).
SCENARIOS = {
    "ingest_step_fails": {
        "ingest_object": {"user_id": "USR-{uid}"},  # last_login_ip omitted -> real KeyError
        "order_events_object": {"orders": [{"order_id": "ORD-{uid}-1", "event_type": "created", "amount": 10.0}]},
    },
    "order_events_step_fails": {
        "ingest_object": {"user_id": "USR-{uid}", "last_login_ip": "10.0.0.1"},
        "order_events_object": {
            "orders": [
                {"order_id": f"ORD-{{uid}}-{i}", "event_type": "created", "amount": 10.0} for i in range(4)
            ],
            "simulate_partial_write_crash": True,
            "crash_after_n_rows": 2,
        },
    },
    "healthy": {
        "ingest_object": {"user_id": "USR-{uid}", "last_login_ip": "10.0.0.1"},
        "order_events_object": {"orders": [{"order_id": "ORD-{uid}-1", "event_type": "created", "amount": 10.0}]},
    },
}


def _sub(obj, uid):
    return json.loads(json.dumps(obj).replace("{uid}", uid))


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in SCENARIOS:
        print(f"Usage: python3 {sys.argv[0]} <{'|'.join(SCENARIOS.keys())}>")
        sys.exit(1)

    scenario = sys.argv[1]
    uid = uuid.uuid4().hex[:6]
    ingest_key = f"customer_profile/PIPELINE-{scenario}-{uid}.json"
    order_events_key = f"order_events/PIPELINE-{scenario}-{uid}.json"

    cfg = SCENARIOS[scenario]
    ingest_object = _sub(cfg["ingest_object"], uid)
    order_events_object = _sub(cfg["order_events_object"], uid)

    s3 = client("s3")
    print(f"Scenario: {scenario}")
    print(f"  Staging s3://{BUCKET_NAME}/{ingest_key}")
    s3.put_object(Bucket=BUCKET_NAME, Key=ingest_key, Body=json.dumps(ingest_object).encode())
    print(f"  Staging s3://{BUCKET_NAME}/{order_events_key}")
    s3.put_object(Bucket=BUCKET_NAME, Key=order_events_key, Body=json.dumps(order_events_object).encode())

    sfn = client("stepfunctions")
    state_machine_arn = None
    for sm in sfn.list_state_machines().get("stateMachines", []):
        if sm["name"] == STATE_MACHINE_NAME:
            state_machine_arn = sm["stateMachineArn"]
            break
    if not state_machine_arn:
        print(f"ERROR: state machine {STATE_MACHINE_NAME} not found -- run provision.py first.")
        sys.exit(1)

    execution_input = {"bucket": BUCKET_NAME, "key": ingest_key}
    exec_name = f"exec-{scenario}-{uid}"
    print(f"  Starting execution {exec_name} on {STATE_MACHINE_NAME} ...")
    start_resp = sfn.start_execution(
        stateMachineArn=state_machine_arn,
        name=exec_name,
        input=json.dumps(execution_input),
    )
    execution_arn = start_resp["executionArn"]

    # Poll for a short window -- LocalStack executes state machines
    # synchronously/quickly for simple Lambda-task chains, but we poll
    # rather than assume immediate completion.
    for _ in range(15):
        desc = sfn.describe_execution(executionArn=execution_arn)
        status = desc["status"]
        if status != "RUNNING":
            break
        time.sleep(1)
    else:
        desc = sfn.describe_execution(executionArn=execution_arn)
        status = desc["status"]

    print(f"  Execution status: {status}")
    print(f"  Output: {desc.get('output')}")
    print(f"\nexecution_arn = {execution_arn}")


if __name__ == "__main__":
    main()
