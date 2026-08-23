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
  duplicate_write       -> writes a batch containing an order_id that was
                          ALREADY successfully committed by an earlier run
                          (a real production symptom of a naive job retry
                          that doesn't check what already landed) -> real
                          psycopg2 UniqueViolation from the genuine
                          order_events_order_id_unique constraint (see
                          migrations/010_order_events_unique_constraint.sql).
  healthy              -> writes the full batch successfully (sanity check,
                          and useful for confirming a rerun worked).

Usage:
    python3 localstack_lab/break_order_events_scenario.py partial_write_crash
    python3 localstack_lab/break_order_events_scenario.py duplicate_write
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

ALL_SCENARIOS = ("partial_write_crash", "duplicate_write", "healthy")


def _make_orders(n: int) -> list:
    return [
        {"order_id": f"ORD-{uuid.uuid4().hex[:8]}", "event_type": "created", "amount": round(19.99 + i, 2)}
        for i in range(n)
    ]


def _invoke(run_id: str, batch: dict) -> None:
    key = f"order_events/{run_id}.json"
    s3 = client("s3")
    s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=json.dumps(batch).encode())
    lam = client("lambda")
    resp = lam.invoke(
        FunctionName=FUNCTION_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps({"bucket": BUCKET_NAME, "key": key, "run_id": run_id}).encode(),
    )
    print(f"  Lambda invoke StatusCode={resp['StatusCode']} FunctionError={resp.get('FunctionError')}")
    print(f"  Payload: {resp['Payload'].read().decode()}")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ALL_SCENARIOS:
        print(f"Usage: python3 {sys.argv[0]} <{'|'.join(ALL_SCENARIOS)}>")
        sys.exit(1)

    scenario = sys.argv[1]
    uid = uuid.uuid4().hex[:6]

    if scenario == "duplicate_write":
        # Two real, sequential Lambda invocations: the first genuinely
        # commits one order successfully; the second batch re-sends the
        # SAME order_id (simulating a retry that forgot to check what
        # already landed), which the real UNIQUE constraint rejects.
        order = {"order_id": f"ORD-DUP-{uid}", "event_type": "created", "amount": 42.0}
        first_run_id = f"RUN-LOCALSTACK-order-events-duplicate_write-first-{uid}"
        second_run_id = f"RUN-LOCALSTACK-order-events-duplicate_write-{uid}"

        print("Scenario: duplicate_write")
        print(f"  Batch: 1 order, run_id={first_run_id}")
        print(f"  First (setup) invocation -- expected to succeed and commit order_id={order['order_id']}:")
        _invoke(first_run_id, {"orders": [order]})
        print()
        print(f"  Second (real failing) invocation -- retries the SAME order_id, run_id={second_run_id}:")
        _invoke(second_run_id, {"orders": [order]})
        print(f"\n  Genuine duplicate-key failure for run_id={second_run_id}.")
        print("  This increments the real CloudWatch 'Errors' metric for the function.")
        return

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
