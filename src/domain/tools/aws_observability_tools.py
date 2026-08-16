"""
Real AWS observability + data-integrity tools for the agent tool-calling
layer. These give the RCA/Runbook/Commander agents the ability to actually
look at what happened (real CloudWatch Logs, real S3 objects) and actually
check/repair real database state (staleness detection, partial-write
cleanup) instead of being limited to NemoGuard's own internal metadata
tables.

Design notes
------------
- All AWS calls go through localstack_lab.aws_clients.client(), which is
  pointed at LocalStack in this environment but would work unmodified
  against real AWS if LOCALSTACK_ENDPOINT/AWS creds were swapped for a
  real account -- same boto3 API surface either way.
- Every function returns a JSON-serializable dict (never raises to the
  caller) so it can be dropped straight into a tool-calling response.
- Destructive operations (cleanup_partial_write) default to dry_run=True
  and require an explicit dry_run=False to actually delete rows, and are
  wrapped in a single transaction scoped to run_id only -- never a
  broader DELETE.
"""

import json
import os
from typing import Optional

import psycopg2
import psycopg2.extras

POSTGRES_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db",
)


def _aws_client(service_name: str):
    """Lazily imports the LocalStack lab's boto3 client factory. Isolated
    into its own function so importing this module doesn't hard-fail in
    environments where the localstack_lab package/boto3 isn't installed
    (e.g. production against real AWS would use its own client setup)."""
    from localstack_lab.aws_clients import client
    return client(service_name)


def query_cloudwatch_logs(log_group_name: str, filter_pattern: str = "", limit: int = 50) -> str:
    """Queries REAL CloudWatch Logs (via LocalStack) for a given log group,
    optionally filtered by a substring pattern. This is the raw
    ground-truth application log stream for a Lambda/Glue job -- richer
    and more complete than NemoGuard's own synthetic log_event table,
    since it includes whatever the function actually printed (stack
    traces, structured logs, etc.), not just what the job's own code
    chose to write back into log_event.
    """
    try:
        logs = _aws_client("logs")
        streams_resp = logs.describe_log_streams(
            logGroupName=log_group_name, orderBy="LastEventTime", descending=True, limit=5
        )
        streams = streams_resp.get("logStreams", [])
        if not streams:
            return json.dumps({"log_group": log_group_name, "events": [], "note": "No log streams found."})

        events = []
        for s in streams:
            resp = logs.get_log_events(
                logGroupName=log_group_name, logStreamName=s["logStreamName"], limit=limit, startFromHead=False
            )
            for e in resp.get("events", []):
                msg = e.get("message", "")
                if filter_pattern and filter_pattern.lower() not in msg.lower():
                    continue
                events.append({"timestamp": e.get("timestamp"), "message": msg})

        events.sort(key=lambda e: e.get("timestamp", 0))
        return json.dumps({"log_group": log_group_name, "filter": filter_pattern, "events": events[-limit:]}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to query CloudWatch Logs for {log_group_name}: {e}"})


def list_s3_objects(bucket: str, prefix: str = "", max_keys: int = 20) -> str:
    """Lists REAL objects in a real (LocalStack) S3 bucket under a prefix,
    so the agent can see exactly what input files existed for a run
    (e.g. to check whether an expected batch file is present/missing, or
    to find related batches from the same time window)."""
    try:
        s3 = _aws_client("s3")
        resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=max_keys)
        objects = [
            {"key": o["Key"], "size": o["Size"], "last_modified": str(o["LastModified"])}
            for o in resp.get("Contents", [])
        ]
        return json.dumps({"bucket": bucket, "prefix": prefix, "objects": objects}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to list s3://{bucket}/{prefix}: {e}"})


def read_s3_object(bucket: str, key: str, max_bytes: int = 4000) -> str:
    """Reads the actual content of a real S3 object (e.g. to inspect the
    exact input data that caused a job to fail -- confirming a schema
    mismatch, malformed record, etc. directly rather than inferring it
    from a stack trace alone)."""
    try:
        s3 = _aws_client("s3")
        obj = s3.get_object(Bucket=bucket, Key=key)
        body = obj["Body"].read()[:max_bytes]
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            text = repr(body)
        return json.dumps({"bucket": bucket, "key": key, "content": text, "truncated": len(body) >= max_bytes})
    except Exception as e:
        return json.dumps({"error": f"Failed to read s3://{bucket}/{key}: {e}"})


def describe_lambda_invocation(function_name: str) -> str:
    """Fetches the real recent CloudWatch metric statistics (Invocations,
    Errors, Duration, Throttles) for a Lambda function, giving the agent
    a quantitative picture of the function's recent health (e.g. "is this
    a one-off failure or part of a sustained error spike?") beyond a
    single log line."""
    try:
        cw = _aws_client("cloudwatch")
        from datetime import datetime, timedelta, timezone
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=30)
        metrics = {}
        for metric_name, stat in [("Invocations", "Sum"), ("Errors", "Sum"), ("Duration", "Average")]:
            resp = cw.get_metric_statistics(
                Namespace="AWS/Lambda",
                MetricName=metric_name,
                Dimensions=[{"Name": "FunctionName", "Value": function_name}],
                StartTime=start,
                EndTime=end,
                Period=300,
                Statistics=[stat],
            )
            datapoints = sorted(resp.get("Datapoints", []), key=lambda d: d["Timestamp"])
            metrics[metric_name] = [{"timestamp": str(d["Timestamp"]), "value": d[stat]} for d in datapoints]

        return json.dumps({"function_name": function_name, "window_minutes": 30, "metrics": metrics}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to describe invocations for {function_name}: {e}"})


def check_table_staleness(table_name: str, run_id: str, expected_row_count: Optional[int] = None) -> str:
    """REAL data-integrity check: compares the actual row count currently
    committed in `table_name` for this run_id against the expected count
    (either passed explicitly, or looked up from
    order_events_run_manifest if this is the order_events table). This is
    the tool an agent MUST use before deciding whether a rerun is safe --
    if actual < expected, there is genuine partial/stale data that needs
    cleanup first, otherwise a naive rerun will double-write the rows
    that already committed.

    Only a small, explicit allowlist of (table_name -> run_id column)
    pairs is supported, to avoid building an arbitrary-SQL tool.
    """
    allowed_tables = {"order_events": "run_id"}
    if table_name not in allowed_tables:
        return json.dumps({"error": f"Table '{table_name}' is not in the allowed staleness-check list: {list(allowed_tables)}"})

    run_id_col = allowed_tables[table_name]
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        with conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(f"SELECT COUNT(*) AS n, MAX(written_at) AS last_write FROM {table_name} WHERE {run_id_col} = %s", (run_id,))
            row = cur.fetchone()
            actual_count = row["n"]
            last_write = str(row["last_write"]) if row["last_write"] else None

            if expected_row_count is None and table_name == "order_events":
                cur.execute("SELECT expected_row_count FROM order_events_run_manifest WHERE run_id = %s", (run_id,))
                manifest_row = cur.fetchone()
                expected_row_count = manifest_row["expected_row_count"] if manifest_row else None

            is_stale = expected_row_count is not None and actual_count < expected_row_count

            return json.dumps({
                "table": table_name,
                "run_id": run_id,
                "actual_row_count": actual_count,
                "expected_row_count": expected_row_count,
                "last_write": last_write,
                "is_stale_or_partial": is_stale,
                "recommendation": (
                    "Partial/stale write detected. Call cleanup_partial_write before rerunning the job."
                    if is_stale else
                    "Row count matches expectation (or no expectation recorded); no cleanup needed."
                ),
            }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Staleness check failed for {table_name}/{run_id}: {e}"})
    finally:
        try:
            conn.close()
        except Exception:
            pass


def cleanup_partial_write(table_name: str, run_id: str, dry_run: bool = True) -> str:
    """Deletes rows in `table_name` belonging to `run_id` -- used to clean
    up a genuine partial write BEFORE a job is rerun, so the rerun starts
    from a clean slate instead of double-writing already-committed rows.

    Safety properties:
      - Scoped ONLY to the given run_id (never a broader/unscoped DELETE).
      - Defaults to dry_run=True: reports how many rows WOULD be deleted
        without deleting anything. The caller (agent) must explicitly
        pass dry_run=False to actually perform the deletion -- this is
        also enforced at the policy layer (see execute_simulated_action's
        risk-gating in src/tools/write_tools.py) since this is a
        destructive action.
    """
    allowed_tables = {"order_events": "run_id"}
    if table_name not in allowed_tables:
        return json.dumps({"error": f"Table '{table_name}' is not in the allowed cleanup list: {list(allowed_tables)}"})

    run_id_col = allowed_tables[table_name]
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {run_id_col} = %s", (run_id,))
            count_before = cur.fetchone()[0]

            if dry_run:
                return json.dumps({
                    "table": table_name, "run_id": run_id, "dry_run": True,
                    "rows_that_would_be_deleted": count_before,
                    "note": "Dry run only -- no rows deleted. Call again with dry_run=False to actually delete.",
                })

            cur.execute(f"DELETE FROM {table_name} WHERE {run_id_col} = %s", (run_id,))
            deleted = cur.rowcount
        conn.commit()

        return json.dumps({
            "table": table_name, "run_id": run_id, "dry_run": False,
            "rows_deleted": deleted,
            "note": f"Deleted {deleted} partial-write rows for run_id={run_id}. Safe to rerun the job now.",
        })
    except Exception as e:
        return json.dumps({"error": f"Cleanup failed for {table_name}/{run_id}: {e}"})
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Additional AWS service coverage: SQS, SNS, RDS, ECS, Step Functions, IAM,
# EC2, Secrets Manager. These extend the tool surface to cover the AWS
# services a real support engineer investigating a data-pipeline/backend
# incident would routinely touch, beyond the Lambda/S3/CloudWatch tools
# above. Same design rules apply: read-only diagnostics are unrestricted;
# anything that changes state is scoped/limited and safe-by-default.
# ---------------------------------------------------------------------------


def get_sqs_queue_attributes(queue_url: str) -> str:
    """Real SQS queue health: current message count, in-flight count, and
    age of the oldest message -- use to check for a backed-up/stuck queue
    (e.g. consumer failure, poison-pill message) or dead-letter queue
    buildup."""
    try:
        sqs = _aws_client("sqs")
        resp = sqs.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=[
                "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible",
                "ApproximateNumberOfMessagesDelayed",
                "RedrivePolicy",
                "CreatedTimestamp",
            ],
        )
        return json.dumps({"queue_url": queue_url, "attributes": resp.get("Attributes", {})}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to get attributes for {queue_url}: {e}"})


def peek_sqs_messages(queue_url: str, max_messages: int = 5) -> str:
    """Reads (without deleting) up to max_messages from an SQS queue -- use
    to inspect what's actually stuck in a queue (e.g. a poison-pill
    message causing repeated consumer failures) without side effects."""
    try:
        sqs = _aws_client("sqs")
        resp = sqs.receive_message(
            QueueUrl=queue_url, MaxNumberOfMessages=max_messages, VisibilityTimeout=1, WaitTimeSeconds=1,
        )
        messages = [{"message_id": m["MessageId"], "body": m["Body"]} for m in resp.get("Messages", [])]
        return json.dumps({"queue_url": queue_url, "messages": messages}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to peek messages on {queue_url}: {e}"})


def list_sns_subscriptions(topic_arn: str) -> str:
    """Lists real subscriptions on an SNS topic -- use to confirm alert
    routing is actually configured as expected (e.g. "is this topic really
    wired to the on-call SQS queue/Lambda/email?")."""
    try:
        sns = _aws_client("sns")
        resp = sns.list_subscriptions_by_topic(TopicArn=topic_arn)
        subs = [{"protocol": s["Protocol"], "endpoint": s["Endpoint"], "subscription_arn": s["SubscriptionArn"]} for s in resp.get("Subscriptions", [])]
        return json.dumps({"topic_arn": topic_arn, "subscriptions": subs}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to list subscriptions for {topic_arn}: {e}"})


def describe_rds_instance_status(db_instance_identifier: str) -> str:
    """Real RDS instance status (availability, storage, CPU-adjacent
    metadata) -- use to check whether a database is in a degraded/failing
    state (storage-full, failing-over, low on connections) as a root
    cause for downstream job failures."""
    try:
        rds = _aws_client("rds")
        resp = rds.describe_db_instances(DBInstanceIdentifier=db_instance_identifier)
        instances = resp.get("DBInstances", [])
        if not instances:
            return json.dumps({"error": f"No RDS instance found: {db_instance_identifier}"})
        inst = instances[0]
        return json.dumps({
            "db_instance_identifier": db_instance_identifier,
            "status": inst.get("DBInstanceStatus"),
            "allocated_storage_gb": inst.get("AllocatedStorage"),
            "engine": inst.get("Engine"),
            "multi_az": inst.get("MultiAZ"),
            "endpoint": inst.get("Endpoint"),
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to describe RDS instance {db_instance_identifier}: {e}"})


def describe_ecs_task_status(cluster: str, service_name: str) -> str:
    """Real ECS service/task status -- use for incidents where a
    containerized job/service (rather than a Lambda) is the failing
    component: checks running vs. desired task count and recent stopped
    tasks with their stop reasons."""
    try:
        ecs = _aws_client("ecs")
        svc_resp = ecs.describe_services(cluster=cluster, services=[service_name])
        services = svc_resp.get("services", [])
        if not services:
            return json.dumps({"error": f"No ECS service found: {service_name} in cluster {cluster}"})
        svc = services[0]

        tasks_resp = ecs.list_tasks(cluster=cluster, serviceName=service_name, desiredStatus="STOPPED", maxResults=5)
        stopped_task_arns = tasks_resp.get("taskArns", [])
        stop_reasons = []
        if stopped_task_arns:
            desc_resp = ecs.describe_tasks(cluster=cluster, tasks=stopped_task_arns)
            stop_reasons = [{"task_arn": t["taskArn"], "stopped_reason": t.get("stoppedReason")} for t in desc_resp.get("tasks", [])]

        return json.dumps({
            "cluster": cluster, "service_name": service_name,
            "running_count": svc.get("runningCount"), "desired_count": svc.get("desiredCount"),
            "pending_count": svc.get("pendingCount"),
            "recent_stopped_tasks": stop_reasons,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to describe ECS service {service_name}: {e}"})


def describe_step_function_execution(execution_arn: str) -> str:
    """Real Step Functions execution status + failure details -- use for
    incidents where the failing job is orchestrated by a state machine
    rather than a single Lambda, to see which state failed and why."""
    try:
        sfn = _aws_client("stepfunctions")
        resp = sfn.describe_execution(executionArn=execution_arn)
        history = sfn.get_execution_history(executionArn=execution_arn, maxResults=10, reverseOrder=True)
        failure_events = [
            {"type": e["type"], "details": e.get(e["type"], {})}
            for e in history.get("events", [])
            if "Fail" in e["type"] or "Aborted" in e["type"]
        ]
        return json.dumps({
            "execution_arn": execution_arn, "status": resp.get("status"),
            "start_date": str(resp.get("startDate")), "stop_date": str(resp.get("stopDate")),
            "recent_failure_events": failure_events,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to describe Step Functions execution {execution_arn}: {e}"})


def check_iam_role_permissions(role_name: str, action: str, resource_arn: str = "*") -> str:
    """Simulates whether an IAM role has permission for a given action on
    a resource (read-only) -- use to diagnose AccessDenied-type failures
    (e.g. "is this the job's IAM role missing s3:GetObject on this
    bucket?") without ever modifying any policy."""
    try:
        iam = _aws_client("iam")
        resp = iam.simulate_principal_policy(
            PolicySourceArn=f"arn:aws:iam::000000000000:role/{role_name}",
            ActionNames=[action],
            ResourceArns=[resource_arn],
        )
        results = [{"action": r["EvalActionName"], "decision": r["EvalDecision"]} for r in resp.get("EvaluationResults", [])]
        return json.dumps({"role_name": role_name, "action": action, "resource_arn": resource_arn, "results": results}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to simulate IAM policy for role {role_name}: {e}"})


def get_secret_metadata(secret_id: str) -> str:
    """Fetches metadata (NOT the secret value) for a Secrets Manager
    secret -- use to check whether a credential rotation happened recently
    (last_changed_date) as a possible cause of a sudden auth failure,
    without ever exposing the actual secret content to the LLM."""
    try:
        sm = _aws_client("secretsmanager")
        resp = sm.describe_secret(SecretId=secret_id)
        return json.dumps({
            "secret_id": secret_id,
            "last_changed_date": str(resp.get("LastChangedDate")),
            "last_rotated_date": str(resp.get("LastRotatedDate")),
            "rotation_enabled": resp.get("RotationEnabled", False),
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to describe secret {secret_id}: {e}"})


def describe_ec2_instance_status(instance_id: str) -> str:
    """Real EC2 instance status checks (system + instance reachability) --
    use when a self-hosted worker/agent running on EC2 (rather than a
    managed service) is suspected to be unhealthy."""
    try:
        ec2 = _aws_client("ec2")
        resp = ec2.describe_instance_status(InstanceIds=[instance_id], IncludeAllInstances=True)
        statuses = resp.get("InstanceStatuses", [])
        if not statuses:
            return json.dumps({"error": f"No status found for instance {instance_id}"})
        s = statuses[0]
        return json.dumps({
            "instance_id": instance_id,
            "instance_state": s.get("InstanceState", {}).get("Name"),
            "system_status": s.get("SystemStatus", {}).get("Status"),
            "instance_status": s.get("InstanceStatus", {}).get("Status"),
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to describe EC2 instance {instance_id}: {e}"})


def list_recent_changes(resource_id: str, window_minutes: int = 60) -> str:
    """
    Change intelligence (spec §8.8): correlates an incident to a specific
    recent deployment/config change rather than guessing -- one of the
    most common real-world root causes is "something changed right before
    this broke."

    Design note: CloudTrail's LookupEvents API is a LocalStack PRO-ONLY
    feature (confirmed via direct testing: returns "API for service
    'cloudtrail' not yet implemented or pro feature" on the free tier).
    Per the platform's "degrade safely" principle (spec §37.4 / non-negotiable
    principle #16 -- never silently substitute a mock success), this
    function does NOT fake CloudTrail data. Instead it uses a genuinely
    free-tier-available, equally real signal: the target Lambda's actual
    `LastModified` timestamp and `RevisionId`/`CodeSha256` from
    `get_function`, which IS real, accurate "when did this resource last
    change" data (a real config/code update genuinely changes these
    fields). If CloudTrail becomes available in a given deployment (e.g.
    LocalStack Pro or real AWS), it is used as an ADDITIONAL, richer
    signal on top of the Lambda-metadata baseline, never as a replacement
    for a case where it's unavailable.
    """
    result = {"resource_id": resource_id, "window_minutes": window_minutes, "changes": []}

    try:
        from datetime import datetime, timedelta, timezone
        lam = _aws_client("lambda")
        fn = lam.get_function(FunctionName=resource_id)
        config = fn.get("Configuration", {})
        last_modified_str = config.get("LastModified")
        if last_modified_str:
            # Lambda's LastModified format: "2026-08-11T18:04:51.788311+0000"
            last_modified = datetime.strptime(last_modified_str, "%Y-%m-%dT%H:%M:%S.%f%z")
            age_minutes = (datetime.now(timezone.utc) - last_modified).total_seconds() / 60
            result["changes"].append({
                "change_type": "LAMBDA_CONFIG_OR_CODE_UPDATE",
                "resource_id": resource_id,
                "last_modified": last_modified_str,
                "age_minutes": round(age_minutes, 1),
                "within_window": age_minutes <= window_minutes,
                "revision_id": config.get("RevisionId"),
                "code_sha256": config.get("CodeSha256"),
                "source": "AWS_LAMBDA_GET_FUNCTION (free-tier, always available)",
            })
    except Exception as e:
        result.setdefault("warnings", []).append(f"Lambda metadata lookup failed: {e}")

    try:
        ct = _aws_client("cloudtrail")
        from datetime import datetime, timedelta, timezone
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=window_minutes)
        resp = ct.lookup_events(
            StartTime=start, EndTime=end,
            LookupAttributes=[{"AttributeKey": "ResourceName", "AttributeValue": resource_id}],
        )
        for e in resp.get("Events", []):
            result["changes"].append({
                "change_type": "CLOUDTRAIL_EVENT",
                "event_name": e.get("EventName"),
                "event_time": str(e.get("EventTime")),
                "username": e.get("Username"),
                "event_source": e.get("EventSource"),
                "source": "AWS_CLOUDTRAIL",
            })
    except Exception as e:
        result.setdefault("warnings", []).append(
            f"CloudTrail unavailable (expected on LocalStack free tier): {e}"
        )

    if not result["changes"]:
        result["note"] = "No recent changes detected for this resource."
    return json.dumps(result, indent=2)


def verify_row_count_matches_expected(table_name: str, run_id: str, expected_row_count: int) -> str:
    """Post-remediation verification: after a rerun (and optional cleanup),
    confirms the table now has EXACTLY the expected row count for this
    run_id -- the real check that should gate whether an incident is
    actually marked resolved, replacing any hardcoded 'resolved: True'
    assumption. Distinct from check_table_staleness (which is a
    pre-action diagnostic) so the agent has a clear, explicit
    "did my fix actually work" verification step to call after remediation."""
    allowed_tables = {"order_events": "run_id"}
    if table_name not in allowed_tables:
        return json.dumps({"error": f"Table '{table_name}' is not in the allowed verification list: {list(allowed_tables)}"})

    run_id_col = allowed_tables[table_name]
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {run_id_col} = %s", (run_id,))
            actual = cur.fetchone()[0]

        matches = actual == expected_row_count
        return json.dumps({
            "table": table_name, "run_id": run_id,
            "actual_row_count": actual, "expected_row_count": expected_row_count,
            "verified": matches,
            "conclusion": "Row count matches expected -- recovery verified successfully." if matches
                          else f"Mismatch: expected {expected_row_count} rows but found {actual}. Recovery NOT verified; do not mark incident resolved.",
        })
    except Exception as e:
        return json.dumps({"error": f"Verification failed for {table_name}/{run_id}: {e}"})
    finally:
        try:
            conn.close()
        except Exception:
            pass
