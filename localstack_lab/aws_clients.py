"""
Shared boto3 client factory for the LocalStack lab.

All scripts in this package talk to a LocalStack container instead of real
AWS — same boto3 API, same request/response shapes, just pointed at a local
endpoint. This means anything wired up here (S3 puts, Lambda invokes,
CloudWatch alarms, SNS publishes) will work unmodified against real AWS if
this project ever needs to graduate from local simulation to a real
account — just delete the endpoint_url override and swap credentials.
"""

import os
import boto3

LOCALSTACK_ENDPOINT = os.environ.get("LOCALSTACK_ENDPOINT", "http://localhost:4566")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# LocalStack ignores these credential values entirely (no real auth), but
# boto3 refuses to build a client without *something* present.
FAKE_CREDS = {
    "aws_access_key_id": "test",
    "aws_secret_access_key": "test",
    "region_name": AWS_REGION,
}


def client(service_name: str, endpoint_url: str = LOCALSTACK_ENDPOINT):
    """Returns a boto3 client for `service_name` pointed at LocalStack."""
    return boto3.client(service_name, endpoint_url=endpoint_url, **FAKE_CREDS)


def resource(service_name: str, endpoint_url: str = LOCALSTACK_ENDPOINT):
    """Returns a boto3 resource for `service_name` pointed at LocalStack."""
    return boto3.resource(service_name, endpoint_url=endpoint_url, **FAKE_CREDS)
