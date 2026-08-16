#!/usr/bin/env python3
"""
Triggers a REAL "poison pill" failure against the notification_job Lambda,
simulating a malformed SQS message that a real SQS-triggered consumer
cannot process.

Scenarios:
  poison_pill  -> message missing "user_id" -> real KeyError in the job.
                  The message is intentionally left in the queue (it's
                  invoked directly, not via a real event-source-mapping),
                  so a SECOND, THIRD, etc. invocation of this scenario
                  simulates the exact "same poison message keeps getting
                  redelivered and crashing the consumer" backup pattern a
                  real SQS+Lambda pipeline exhibits without a DLQ.
  healthy      -> a fully valid message -> succeeds normally. Use this
                  to confirm the queue is draining again after an agent's
                  remediation (e.g. purging/redirecting the bad message).

Usage:
    python3 localstack_lab/break_notification_scenario.py poison_pill
    python3 localstack_lab/break_notification_scenario.py healthy
"""

import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(__file__))
from aws_clients import client  # noqa: E402

FUNCTION_NAME = "nemoguard-notification-job"
QUEUE_NAME = "nemoguard-notifications-queue"

SCENARIOS = {
    "poison_pill": {
        # "user_id" intentionally omitted
        "simulate_poison_pill": True,
    },
    "healthy": {
        "user_id": "USR-{uid}",
    },
}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in SCENARIOS:
        print(f"Usage: python3 {sys.argv[0]} <{'|'.join(SCENARIOS.keys())}>")
        sys.exit(1)

    scenario = sys.argv[1]
    uid = uuid.uuid4().hex[:6]
    run_id = f"RUN-LOCALSTACK-notification-{scenario}-{uid}"

    body = json.loads(json.dumps(SCENARIOS[scenario]).replace("{uid}", uid))

    sqs = client("sqs")
    queue_url = sqs.create_queue(QueueName=QUEUE_NAME)["QueueUrl"]

    print(f"Scenario: {scenario}")
    print(f"  Sending message to {QUEUE_NAME}: {body}")
    send_resp = sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(body))
    print(f"  MessageId: {send_resp['MessageId']}")

    print(f"  Invoking {FUNCTION_NAME} against it (run_id={run_id}) ...")
    lam = client("lambda")
    resp = lam.invoke(
        FunctionName=FUNCTION_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps({"run_id": run_id, "message_body": body}).encode(),
    )
    payload = resp["Payload"].read().decode()
    status_code = resp.get("StatusCode")
    function_error = resp.get("FunctionError")

    print(f"  Lambda StatusCode: {status_code}")
    if function_error:
        print(f"  FunctionError: {function_error} (this is the REAL failure -- not scripted)")
        print(f"  Payload: {payload}")
        print("\n  The message remains on the queue (visible again after the visibility")
        print("  timeout) -- run `get_sqs_queue_attributes` against this queue to observe")
        print("  the real backup, or re-run this scenario to simulate repeated redelivery.")
    else:
        print(f"  Payload: {payload}")
        print("\n  Job succeeded -- run_id and result are real, written by the real handler.")

    print(f"\nrun_id = {run_id}")
    print(f"queue_url = {queue_url}")


if __name__ == "__main__":
    main()
