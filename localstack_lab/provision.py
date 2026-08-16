#!/usr/bin/env python3
"""
Provisions the baseline AWS resources for the NemoGuard LocalStack lab:

  1. S3 bucket        `nemoguard-lab-data`             (holds simulated upstream extracts)
  2. Lambda function  `nemoguard-ingest-job`           (real job: S3 -> validate -> Postgres,
                                                          schema-drift / OOM / DB-outage scenarios)
  3. Lambda function  `nemoguard-order-events-job`     (real Glue-style job: S3 -> writes
                                                          order_events row-by-row, genuine
                                                          partial-write-on-crash scenario)
  4. CloudWatch Alarms `nemoguard-ingest-job-errors`,
                       `nemoguard-order-events-job-errors` (fire on each function's real
                                                          Errors metric)
  5. SNS topic         `nemoguard-lab-alerts`           (both Alarms publish here)
  6. SQS queue         `nemoguard-lab-alerts-queue`     (subscribed to the SNS topic; the
                                                          forwarder polls this queue and
                                                          translates messages into NemoGuard
                                                          webhook payloads)

Run this once after `docker compose up -d localstack` (or any time you want
to reset the lab back to a clean baseline -- it's idempotent).

Usage:
    python3 localstack_lab/provision.py
"""

import io
import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from aws_clients import client  # noqa: E402

LAB_DIR = Path(__file__).parent

BUCKET_NAME = "nemoguard-lab-data"
TOPIC_NAME = "nemoguard-lab-alerts"
QUEUE_NAME = "nemoguard-lab-alerts-queue"
NOTIFICATIONS_QUEUE_NAME = "nemoguard-notifications-queue"

# Each lab job: (function_name, source_dir_name)
LAB_FUNCTIONS = [
    ("nemoguard-ingest-job", "ingest_job"),
    ("nemoguard-order-events-job", "order_events_job"),
    ("nemoguard-notification-job", "notification_job"),
]

POSTGRES_URL_FOR_LAMBDA = os.environ.get(
    "POSTGRES_URL_FOR_LAMBDA",
    # From inside a LocalStack Lambda container, "postgres" resolves via the
    # shared docker-compose network (see localstack service's `networks` in
    # docker-compose.yml). If running provision.py from the host instead of
    # in-container, override via env var to point at localhost.
    "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db",
)
LOCALSTACK_ENDPOINT_FOR_LAMBDA = os.environ.get(
    "LOCALSTACK_ENDPOINT_FOR_LAMBDA", "http://localstack:4566"
)


def _build_lambda_zip(source_dir_name: str) -> bytes:
    """Builds the Lambda deployment zip for a given lambda_src/<name>/
    directory. Dependencies (psycopg2-binary) are installed inside a
    temporary Linux container so the compiled extension matches the
    Lambda runtime's platform regardless of what OS this script runs on
    (e.g. building on macOS for a linux/amd64 Lambda runtime)."""
    src_dir = LAB_DIR / "lambda_src" / source_dir_name
    build_dir = LAB_DIR / "_build" / source_dir_name
    build_dir.mkdir(parents=True, exist_ok=True)

    print(f"  Installing Lambda dependencies for {source_dir_name} (via a throwaway linux container)...")
    subprocess.run(
        [
            "docker", "run", "--rm",
            "-v", f"{src_dir.resolve()}:/src:ro",
            "-v", f"{build_dir.resolve()}:/build",
            "--platform", "linux/amd64",
            "public.ecr.aws/sam/build-python3.10",
            "pip", "install", "-r", "/src/requirements.txt", "-t", "/build",
        ],
        check=True,
    )

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(src_dir / "handler.py", "handler.py")
        for root, _dirs, files in os.walk(build_dir):
            for f in files:
                full = Path(root) / f
                arcname = str(full.relative_to(build_dir))
                zf.write(full, arcname)
    return zip_buf.getvalue()


def _wait_for_lambda_update(lam, function_name: str, timeout_sec: int = 30) -> None:
    """Polls get_function until the function's LastUpdateStatus is no
    longer 'InProgress', so subsequent update_function_* calls don't race
    LocalStack's async update and hit ResourceConflictException."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        resp = lam.get_function(FunctionName=function_name)
        status = resp["Configuration"].get("LastUpdateStatus", "Successful")
        if status != "InProgress":
            return
        time.sleep(1)


def ensure_bucket(s3):
    print(f"  S3 bucket: {BUCKET_NAME}")
    try:
        s3.create_bucket(Bucket=BUCKET_NAME)
    except s3.exceptions.BucketAlreadyOwnedByYou:
        pass
    except Exception as e:
        if "BucketAlreadyExists" not in str(e) and "BucketAlreadyOwnedByYou" not in str(e):
            raise


def ensure_lambda(lam, function_name: str, source_dir_name: str):
    print(f"  Lambda function: {function_name}")
    zip_bytes = _build_lambda_zip(source_dir_name)

    env_vars = {
        "POSTGRES_URL": POSTGRES_URL_FOR_LAMBDA,
        "LOCALSTACK_ENDPOINT": LOCALSTACK_ENDPOINT_FOR_LAMBDA,
    }

    existing = None
    try:
        existing = lam.get_function(FunctionName=function_name)
    except lam.exceptions.ResourceNotFoundException:
        pass

    if existing:
        lam.update_function_code(FunctionName=function_name, ZipFile=zip_bytes)
        _wait_for_lambda_update(lam, function_name)
        lam.update_function_configuration(
            FunctionName=function_name,
            Environment={"Variables": env_vars},
            Timeout=30,
            MemorySize=256,
        )
        _wait_for_lambda_update(lam, function_name)
    else:
        lam.create_function(
            FunctionName=function_name,
            Runtime="python3.10",
            Role="arn:aws:iam::000000000000:role/lambda-role",  # LocalStack ignores real IAM
            Handler="handler.handler",
            Code={"ZipFile": zip_bytes},
            Timeout=30,
            MemorySize=256,
            Environment={"Variables": env_vars},
        )
    time.sleep(2)


def ensure_sns_and_sqs(sns, sqs):
    print(f"  SNS topic: {TOPIC_NAME}")
    topic_arn = sns.create_topic(Name=TOPIC_NAME)["TopicArn"]

    print(f"  SQS queue: {QUEUE_NAME}")
    queue_url = sqs.create_queue(QueueName=QUEUE_NAME)["QueueUrl"]
    queue_attrs = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])
    queue_arn = queue_attrs["Attributes"]["QueueArn"]

    sns.subscribe(TopicArn=topic_arn, Protocol="sqs", Endpoint=queue_arn)

    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": "*",
            "Action": "sqs:SendMessage",
            "Resource": queue_arn,
            "Condition": {"ArnEquals": {"aws:SourceArn": topic_arn}},
        }],
    }
    sqs.set_queue_attributes(QueueUrl=queue_url, Attributes={"Policy": json.dumps(policy)})

    return topic_arn, queue_url


STATE_MACHINE_NAME = "nemoguard-daily-pipeline"


def ensure_state_machine(sfn, lam, iam):
    """Provisions a real Step Functions state machine chaining
    nemoguard-ingest-job -> nemoguard-order-events-job, so an agent can be
    tested against an incident where the ROOT CAUSE is a specific state
    in a multi-step orchestrated pipeline, not a single standalone Lambda.
    This is what `describe_step_function_execution` was built to inspect."""
    print(f"  Step Functions state machine: {STATE_MACHINE_NAME}")

    ingest_fn = lam.get_function(FunctionName="nemoguard-ingest-job")["Configuration"]["FunctionArn"]
    order_events_fn = lam.get_function(FunctionName="nemoguard-order-events-job")["Configuration"]["FunctionArn"]

    definition = {
        "Comment": "Daily pipeline: ingest customer_profile batch, then process order_events batch.",
        "StartAt": "IngestCustomerProfile",
        "States": {
            "IngestCustomerProfile": {
                "Type": "Task",
                "Resource": ingest_fn,
                "Next": "ProcessOrderEvents",
                "Catch": [{"ErrorEquals": ["States.ALL"], "Next": "PipelineFailed"}],
            },
            "ProcessOrderEvents": {
                "Type": "Task",
                "Resource": order_events_fn,
                "End": True,
                "Catch": [{"ErrorEquals": ["States.ALL"], "Next": "PipelineFailed"}],
            },
            "PipelineFailed": {
                "Type": "Fail",
                "Error": "PipelineStepFailed",
                "Cause": "One of the pipeline's Lambda steps raised an unhandled exception.",
            },
        },
    }

    role_arn = "arn:aws:iam::000000000000:role/stepfunctions-lab-role"

    existing_arn = None
    for sm in sfn.list_state_machines().get("stateMachines", []):
        if sm["name"] == STATE_MACHINE_NAME:
            existing_arn = sm["stateMachineArn"]
            break

    if existing_arn:
        sfn.update_state_machine(
            stateMachineArn=existing_arn,
            definition=json.dumps(definition),
            roleArn=role_arn,
        )
        return existing_arn

    resp = sfn.create_state_machine(
        name=STATE_MACHINE_NAME,
        definition=json.dumps(definition),
        roleArn=role_arn,
        type="STANDARD",
    )
    return resp["stateMachineArn"]


def ensure_alarm(cw, function_name: str, topic_arn: str):
    alarm_name = f"{function_name}-errors"
    print(f"  CloudWatch alarm: {alarm_name}")
    cw.put_metric_alarm(
        AlarmName=alarm_name,
        ComparisonOperator="GreaterThanOrEqualToThreshold",
        EvaluationPeriods=1,
        MetricName="Errors",
        Namespace="AWS/Lambda",
        Period=60,
        Statistic="Sum",
        Threshold=1.0,
        ActionsEnabled=True,
        AlarmActions=[topic_arn],
        AlarmDescription=f"Fires when {function_name} raises an unhandled exception.",
        Dimensions=[{"Name": "FunctionName", "Value": function_name}],
    )
    return alarm_name


def ensure_notifications_queue(sqs):
    print(f"  SQS queue: {NOTIFICATIONS_QUEUE_NAME}")
    queue_url = sqs.create_queue(QueueName=NOTIFICATIONS_QUEUE_NAME)["QueueUrl"]
    return queue_url


def main():
    print("Provisioning NemoGuard LocalStack lab resources...")
    s3 = client("s3")
    lam = client("lambda")
    sns = client("sns")
    sqs = client("sqs")
    cw = client("cloudwatch")
    sfn = client("stepfunctions")
    iam = client("iam")

    ensure_bucket(s3)

    for function_name, source_dir_name in LAB_FUNCTIONS:
        ensure_lambda(lam, function_name, source_dir_name)

    topic_arn, queue_url = ensure_sns_and_sqs(sns, sqs)
    notifications_queue_url = ensure_notifications_queue(sqs)
    state_machine_arn = ensure_state_machine(sfn, lam, iam)

    alarm_names = []
    for function_name, _ in LAB_FUNCTIONS:
        alarm_names.append(ensure_alarm(cw, function_name, topic_arn))

    print("\nDone. Baseline resources:")
    print(f"  S3 bucket:      {BUCKET_NAME}")
    for function_name, _ in LAB_FUNCTIONS:
        print(f"  Lambda:         {function_name}")
    print(f"  SNS topic ARN:  {topic_arn}")
    print(f"  SQS queue URL:  {queue_url}")
    print(f"  SQS notifications queue URL: {notifications_queue_url}")
    print(f"  Step Functions state machine ARN: {state_machine_arn}")
    for alarm_name in alarm_names:
        print(f"  CloudWatch alarm: {alarm_name}")
    print("\nNext: run `python3 localstack_lab/forwarder.py` to start forwarding")
    print("alarm notifications to NemoGuard's /api/v2/ingest/webhook, then run one of:")
    print("  python3 localstack_lab/break_scenario.py <scenario>              (ingest_job)")
    print("  python3 localstack_lab/break_order_events_scenario.py <scenario> (partial-write)")
    print("  python3 localstack_lab/break_notification_scenario.py <scenario> (SQS poison-pill)")
    print("  python3 localstack_lab/break_pipeline_scenario.py <scenario>     (Step Functions)")


if __name__ == "__main__":
    main()
