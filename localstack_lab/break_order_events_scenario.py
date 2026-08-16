#!/usr/bin/env python3
"""
Triggers a REAL partial-write failure in the order_events lab job -- this
is the "Glue job crashed mid-write to a database table" scenario. Uploads a
batch of order events to S3, invokes the real `nemoguard-order-events-job`
Lambda with `simulate_partial_write_crash: true`, and the Lambda genuinely
commits some rows to the real `order_events` table before raising an
exception partway through the batch -- exactly like a real Spark/Glue JDBC
sink crash mid-write.

Scenarios:
  partial_write_crash  -> writes half the batch, then genuinely crashes;
                          real partial data ends up in order_events.
  healthy              -> writes the full batch successfully (sanity check,
                          and useful for confirming a rerun worked).

Usage:
    python3 localstack_lab/break_order_events_scenario.py partial_write_crash
    python3 localstack_lab/break_order_events_scenario.py healthy
"""

import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(__file__))
from aws_clients import client  # noqa: E402

BUCKET_NAME = "nemoguard-lab-data"
FUNCTION_NAME = "nemoguard-order-events-job"


def _make_orders(n: int) -> list:
    return [
        {"order_id": f"ORD-{uuid.uuid4().hex[:8]}", "event_type": "created", "amount": round(19.99 + i, 2)}
        for i in range(n)
    ]


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("partial_write_crash", "healthy"):
        print(f"Usage: python3 {sys.argv[0]} <partial_write_crash|healthy>")
        sys.exit(1)

    scenario = sys.argv[1]
    uid = uuid.uuid4().hex[:6]
    run_id = f"RUN-LOCALSTACK-order-events-{scenario}-{uid}"
    key = f"order_events/{run_id}.json"

    orders = _make_orders(10)
    batch = {"orders": orders}
    if scenario == "partial_write_crash":
        batch["simulate_partial_write_crash"] = True
        batch["crash_after_n_rows"] = 5

    print(f"Scenario: {scenario}")
    print(f"  Batch: {len(orders)} orders, run_id={run_id}")
    print(f"  Uploading s3://{BUCKET_NAME}/{key} ...")
    s3 = client("s3")
    s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=json.dumps(batch).encode())

    print(f"  Invoking {FUNCTION_NAME} ...")
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
        print(f"\n  Genuine partial-write failure for run_id={run_id}.")
        print(f"  Expected row count: {len(orders)}. Some rows are REALLY committed in")
        print("  order_events, some are missing -- this is a real partial-write state,")
        print("  not a simulated one. Use check_table_staleness('order_events', "
              f"'{run_id}') to confirm.")
    else:
        print(f"\n  Job succeeded normally for run_id={run_id} (as expected for 'healthy').")


if __name__ == "__main__":
    main()
