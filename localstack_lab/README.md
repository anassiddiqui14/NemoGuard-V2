# NemoGuard LocalStack Lab

Simulates **real AWS services locally** (via [LocalStack](https://www.localstack.cloud/))
so you can test how effective NemoGuard's agents actually are against a
genuine (if local) cloud data pipeline — not just scripted webhook payloads.

## Why this exists

The existing `simulator_backend/` fires **hand-scripted** webhook JSON at
NemoGuard's ingestion endpoint. It's great for demoing UI flows, but it
can't tell you whether the agents' *recovery actions* actually fix
anything, because there's no real infrastructure underneath to break or
repair.

This lab adds:
- A real S3 bucket, a real AWS Lambda function, a real CloudWatch Alarm,
  and a real SNS→SQS fan-out — all running against LocalStack (same
  `boto3` API surface as real AWS, just pointed at `localhost:4566`).
- A tiny but genuine data-pipeline job (`nemoguard-ingest-job`) that reads
  a JSON object from S3, validates it, and writes to the same Postgres
  database NemoGuard already uses. It can genuinely fail in 3 different
  ways (schema drift / OOM / DB outage) — no "pretend to fail" flags.
- A forwarder that translates real CloudWatch Alarm→SNS notifications into
  NemoGuard's existing webhook JSON shape (same endpoint the simulator
  already posts to — no changes needed on the NemoGuard side).
- Real remediation + verification wired into `src/tools/write_tools.py`
  (feature-flagged, off by default) so `execute_simulated_action` actually
  re-invokes the real Lambda, and `verify_incident_recovery` actually
  checks real Postgres + CloudWatch state instead of hardcoding success.

## Setup

### 1. Start the lab

```bash
cd pipeline-copilot
docker compose --profile lab up -d localstack
# wait ~10s for LocalStack's health check to pass
docker compose --profile lab logs -f localstack   # Ctrl+C once healthy
```

### 2. Install lab dependencies (for running the Python scripts from your host)

```bash
pip install -r localstack_lab/requirements.txt
```

You also need Docker running locally (the provisioning script uses a
throwaway `public.ecr.aws/sam/build-python3.10` container to build the
Lambda's dependency bundle with the correct Linux binaries).

### 3. Provision baseline AWS resources

```bash
python3 localstack_lab/provision.py
```

This creates the S3 bucket, deploys the Lambda, and sets up the
CloudWatch Alarm + SNS topic + SQS queue. Safe to re-run any time (it's
idempotent) — e.g. after editing `lambda_src/ingest_job/handler.py`.

### 4. Start the forwarder (leave this running in its own terminal)

```bash
python3 localstack_lab/forwarder.py
```

This polls the SQS queue and forwards real CloudWatch Alarm notifications
into NemoGuard's `/api/v2/ingest/webhook` endpoint, exactly like a real
CloudWatch→SNS→subscriber integration would in production.

### 5. Break something for real

```bash
python3 localstack_lab/break_scenario.py schema_drift   # missing field -> KeyError
python3 localstack_lab/break_scenario.py oom_crash       # real MemoryError
python3 localstack_lab/break_scenario.py db_outage       # real connection failure
python3 localstack_lab/break_scenario.py healthy         # sanity check: succeeds normally
```

Within ~1 minute, the CloudWatch Alarm should trip and the forwarder
should push a webhook into NemoGuard, kicking off the normal
Watcher→RCA→Impact→Runbook→Commander→Safety pipeline — but this time
sourced from a genuine AWS Lambda failure instead of a scripted payload.

### 6. (Optional) Enable real remediation + verification

By default, when NemoGuard's agents "execute" a recovery plan and
"verify" the incident is resolved, those tool calls are no-ops that
always report success (see `src/tools/write_tools.py`). To make them do
(and check) something real against this lab:

```bash
# In pipeline-copilot/.env or your shell:
export NEMOGUARD_LOCALSTACK_LAB=1

# Restart the api service with this env var + the lab profile:
docker compose --profile lab up -d --force-recreate api
```

With this enabled, `execute_simulated_action` re-invokes the real Lambda
with a corrected payload, and `verify_incident_recovery` checks the real
`execution` table in Postgres *and* the real CloudWatch alarm state
before reporting `resolved: true` — so a bad recovery plan will now
genuinely show up as "not resolved."

## Files

| File | Purpose |
|---|---|
| `aws_clients.py` | Shared boto3 client factory pointed at LocalStack |
| `provision.py` | Creates S3/Lambda(s)/CloudWatch/SNS/SQS baseline resources |
| `lambda_src/ingest_job/handler.py` | Real S3->Postgres job with schema-drift/OOM/DB-outage failure modes |
| `lambda_src/order_events_job/handler.py` | Real Glue-style job writing to `order_events` row-by-row, with a genuine mid-batch partial-write crash mode |
| `forwarder.py` | Polls SQS, translates alarms into NemoGuard webhook payloads |
| `break_scenario.py` | Triggers ingest_job failures (schema_drift / oom_crash / db_outage / healthy) |
| `break_order_events_scenario.py` | Triggers the order_events partial-write-crash scenario |
| `remediate.py` | Real remediation/verification helpers used by `write_tools.py`, including `idempotent_rerun_order_events_job` (staleness check -> cleanup -> rerun -> verify) |

## Agent capability upgrade: real observability + safe write-job remediation

When `NEMOGUARD_LOCALSTACK_LAB=1`, agents get access to real tools beyond
NemoGuard's own metadata tables (defined in
`src/domain/tools/aws_observability_tools.py`, wired into
`src/domain/agents/agent_tools.py`):

- `query_cloudwatch_logs` — the real, complete application log stream for a
  Lambda (not just what it echoed back into NemoGuard's log_event table).
- `list_s3_objects` / `read_s3_object` — inspect the actual input file that
  caused a failure.
- `describe_lambda_invocation` — real Invocations/Errors/Duration metrics.
- `check_table_staleness` — REQUIRED before recommending a rerun of any
  job that writes to a database table (currently supports `order_events`):
  compares actual vs. expected row count for a run_id to detect a genuine
  partial write.
- `cleanup_partial_write` — deletes partial rows for a run_id (dry-run by
  default) before a safe rerun.
- `verify_row_count_matches_expected` — post-remediation check that a
  rerun actually restored the expected data, instead of assuming success.

This is structurally enforced, not just prompted: the `RunbookAgent`'s
prompt states the required ordering (check -> cleanup if needed -> rerun ->
verify), and the `GroundingCritic` (`langgraph_investigator.py`) independently
re-validates the actual proposed steps and forces `passed: false` if a
write-job rerun is proposed without a preceding staleness check, regardless
of what the LLM itself claims.

Test this end-to-end:

```bash
python3 localstack_lab/break_order_events_scenario.py partial_write_crash
# creates a REAL partial write (some rows committed, some missing)

python3 -c "
from localstack_lab.remediate import idempotent_rerun_order_events_job
orders = [{'order_id': f'ORD-{i}', 'event_type': 'created', 'amount': 10.0} for i in range(10)]
print(idempotent_rerun_order_events_job('<run_id from above>', orders))
"
# detects the staleness, cleans up the partial rows, reruns, verifies -- all real
```

## Tearing down

```bash
docker compose --profile lab down -v   # -v also removes the localstack_data volume
