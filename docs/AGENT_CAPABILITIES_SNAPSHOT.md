# NemoGuard Agentic Capabilities — Current State Snapshot

_Generated for external review (e.g. feeding into another LLM) to identify
gaps in tooling for a "support engineer" agent working with AWS services._

---

## 1. Architecture Overview

NemoGuard is an agentic incident-response system for data pipelines. When an
alert comes in, a chain of specialized LLM agents investigates, formulates a
recovery plan, gets it critiqued for safety, and (after human approval)
executes it. Orchestration is via LangGraph (investigation phase) + Temporal
(workflow durability/retries).

**Pipeline (in order of execution):**

```
Webhook/Alert
    -> Watcher Agent          (classify: real signal? noise? recovery signal? correlate to existing incident?)
    -> RCA Agent              (root cause analysis, using tools)
    -> [Impact Agent | Runbook Agent]  (run in parallel, both grounded in RCA's finding)
    -> Grounding Critic        (Safety Agent) — validates evidence grounding, produces final_plan
    -> [Human Approval Gate]
    -> Execution               (currently: marks steps SUCCEEDED, no real actions unless LocalStack lab is enabled)
    -> Verification            (currently: hardcoded PASSED, unless LocalStack lab is enabled)
```

All agents are backed by NVIDIA Nemotron models via the OpenAI-compatible
API (`nvidia/nemotron-3-super-120b-a12b` for lighter agents,
`nvidia/nemotron-3-ultra-550b-a55b` for RCA + the Grounding Critic — the two
most consequential decision points).

---

## 2. Agents and Their Current Responsibilities

| Agent | Model | Role | Tools available today |
|---|---|---|---|
| **Watcher Agent** | nemotron-3-super-120b | Classifies incoming webhook payloads as real/noise, detects recovery signals, correlates to existing incidents | None (pure LLM reasoning over the payload + list of active incidents) |
| **RCA Agent** | nemotron-3-ultra-550b | Root cause analysis — the most consequential decision in the pipeline | `query_logs` (+ LocalStack-lab-only tools, see §3) |
| **Dependency/Impact Agent** | nemotron-3-super-120b | Determines downstream blast radius via CMDB | `get_cmdb_context` |
| **Runbook Agent** | nemotron-3-super-120b | Retrieves/matches standard operating procedures, proposes recovery steps | `get_runbook` (+ LocalStack-lab-only tools) |
| **Grounding Critic (aka "Safety Agent")** | nemotron-3-ultra-550b | Final safety gate: checks evidence grounding, combines findings into `final_plan`, can reject (`passed: false`) | None directly, but re-validates the actual RCA+Runbook output structurally (see §4) |
| **Commander Agent** | nemotron-3-ultra-550b | (Legacy/fallback path) Synthesizes all sub-agent findings into one plan in a single call, used when the LangGraph flow isn't used | None (pure synthesis over already-collected data) |

**Notably absent:** there is no agent step that actually *executes* recovery
actions using tools during the investigation phase — the agents only
*propose* a plan (as free-text `action`/`tool_name` strings). The actual
execution phase (`execute_plan` in `orchestrator.py` / `write_tools.py`) is
separate and, by default, does nothing real (see §5).

---

## 3. Tool Inventory (what agents can actually *do*, not just reason about)

### 3a. Always available (NemoGuard's own metadata, SQLite/Postgres-backed)

| Tool | What it does | Read/Write | Scope limitation |
|---|---|---|---|
| `query_logs(incident_id, keyword?)` | Reads NemoGuard's own `log_event` table for the incident's `primary_run_id` | Read | Only sees what the *simulator/lab job itself chose to write back* into this table — not real infra logs |
| `get_cmdb_context(service_name)` | Reads NemoGuard's own `job`/`business_asset`/`asset_dependency` tables | Read | Synthetic CMDB, not a real service-catalog/dependency-graph integration |
| `get_runbook(service_name)` | Reads NemoGuard's own `runbook` table | Read | Static seed data, not a real runbook/wiki integration |

### 3b. Only available when `NEMOGUARD_LOCALSTACK_LAB=1` (real AWS API surface, via LocalStack)

Added specifically to give agents access to *real* infrastructure signal
instead of only NemoGuard's own synthetic tables. All go through boto3
pointed at LocalStack (same API shape as real AWS; would work against a
real account unmodified).

| Tool | AWS Service | What it does | Read/Write | Safety notes |
|---|---|---|---|---|
| `query_cloudwatch_logs` | CloudWatch Logs | Full raw application log stream for a Lambda | Read | — |
| `list_s3_objects` | S3 | Lists objects under a prefix | Read | — |
| `read_s3_object` | S3 | Reads object content | Read | Truncated to 4KB |
| `describe_lambda_invocation` | Lambda + CloudWatch | Invocations/Errors/Duration metrics, last 30 min | Read | — |
| `check_table_staleness` | Postgres (app DB) | Compares actual vs. expected row count for a run_id | Read | Table allowlist: `order_events` only |
| `cleanup_partial_write` | Postgres (app DB) | Deletes rows for a run_id | **Write (destructive)** | dry_run=True by default; scoped to single run_id; table allowlist |
| `verify_row_count_matches_expected` | Postgres (app DB) | Post-remediation row-count check | Read | Table allowlist |
| `get_sqs_queue_attributes` | SQS | Queue depth / in-flight / DLQ signals | Read | — |
| `peek_sqs_messages` | SQS | Reads (no delete) up to N messages | Read | — |
| `list_sns_subscriptions` | SNS | Lists topic subscriptions | Read | — |
| `describe_rds_instance_status` | RDS | Instance status/storage/engine/Multi-AZ | Read | — |
| `describe_ecs_task_status` | ECS | Running/desired task count + stopped-task reasons | Read | — |
| `describe_step_function_execution` | Step Functions | Execution status + recent failure events | Read | — |
| `check_iam_role_permissions` | IAM | Simulates (read-only) whether a role has a permission | Read | Never modifies policy |
| `get_secret_metadata` | Secrets Manager | Rotation timestamps only | Read | **Never returns the secret value itself** |
| `describe_ec2_instance_status` | EC2 | System/instance status checks | Read | — |

### 3c. Execution-side "actions" (not agent tools — separate code path)

These are invoked *after* human approval, currently mostly no-ops:

| Function | Location | Current behavior |
|---|---|---|
| `execute_simulated_action` | `src/tools/write_tools.py` | Default: writes an audit row only, no real action. With lab flag: can call `rerun_ingest_job` (re-invoke a specific Lambda) or `idempotent_rerun_order_events_job` (check→cleanup→rerun→verify sequence, but ONLY for the one hardcoded `order_events` table/job pair) |
| `verify_incident_recovery` | `src/tools/write_tools.py` | Default: hardcoded `resolved: True`. With lab flag: checks real `execution` table status + real CloudWatch alarm state |
| `execute_plan` | `src/domain/orchestrator.py` | Marks DB rows as `EXECUTED`/`SUCCEEDED`, inserts two hardcoded "PASSED" verification_result rows — **does not call any tool or perform any real action** regardless of lab flag |

---

## 4. What's Structurally Enforced vs. Just Prompted

- **Prompted only** (relies on the LLM following instructions, not code-enforced): agents are *told* which tools to call and in what order via system prompts (e.g. "call `get_runbook` at most once", "you MUST call `check_table_staleness` before any rerun step").
- **Structurally enforced** (code re-validates the LLM's actual output): the `GroundingCritic` step in `langgraph_investigator.py` has a hard-coded post-check (`_plan_violates_data_integrity_policy`) that inspects the *actual returned plan steps* and forces `passed: false` if a write-job rerun is proposed without a preceding staleness-check step — this is the one place where policy is enforced in code rather than trusted from the LLM.

---

## 5. Known Gaps (as of this snapshot)

1. **No general execution engine.** Recovery "steps" are free-text strings (`action`, `tool_name`) with no formal mapping to a callable function except for the two hardcoded LocalStack-lab paths (`ingest_job`, `order_events`). There's no generic "here's a tool name + args, go call it" execution loop during the approved-plan-execution phase — only during the *investigation* phase (tool-calling agents).
2. **Tool allowlists are single-table/single-function.** `check_table_staleness`/`cleanup_partial_write`/`verify_row_count_matches_expected` only know about the `order_events` table. Adding a new write-job target currently requires editing the allowlist in `aws_observability_tools.py` by hand.
3. **No write/mutating tools for most AWS services.** Everything in §3b except the Postgres cleanup tool is read-only. There is no `restart_ecs_service`, `retry_step_function_execution`, `redrive_dlq_messages`, `scale_asg`, `reboot_rds_instance`, `rotate_secret`, `terminate_and_replace_ec2_instance`, etc. — an agent can *diagnose* using ECS/RDS/SQS/StepFunctions/EC2/IAM/Secrets tools, but cannot *act* on any of them.
4. **No cost/budget awareness.** No tool for Cost Explorer / Budgets — an agent can't reason about "will this remediation blow the budget" or catch a cost-anomaly-driven incident.
5. **No network/security-group tooling.** No VPC/Security Group/NACL inspection — common root cause for "job can't reach X" type incidents.
6. **No CloudTrail tool.** No way to answer "who/what last changed this resource" — useful for correlating a config-drift-caused incident to a specific deploy/change event.
7. **No generic "run an arbitrary read query against the actual downstream data warehouse/lake" tool** (e.g. Athena, Redshift query execution) — agents can inspect S3 files raw, but can't query structured data at scale.
8. **No deployment/CI tool integration** (e.g. checking recent CodeDeploy/CodePipeline history) to correlate an incident to a recent deploy.
9. **No cross-account/cross-region tooling** — everything assumes single-account, single-region (matches the LocalStack lab's scope, but real support engineers often work across accounts).
10. **Watcher Agent and Impact/Dependency Agent have zero tools beyond their one narrow lookup** — no ability for the Watcher to, say, check CloudWatch itself to corroborate an ambiguous alert before classifying it.

---

## 6. Summary for External Review

If evaluating this system's readiness to act as an autonomous "AWS support
engineer," the key question to answer is: **given the diagnostic tool
coverage in §3b, what is the minimal set of *safe, scoped, write/mutating*
tools needed to let the agent actually resolve (not just diagnose) the most
common categories of incidents it will encounter?**

Concretely useful framing for that review:

- For each read-only diagnostic tool already listed in §3b, is there a
  natural, safe "fix" action a real support engineer would take after
  seeing that diagnostic result? (e.g. after `describe_ecs_task_status`
  shows `running_count < desired_count` with a repeated OOM stop reason →
  what's the safe action? Force a new deployment? Bump memory and
  redeploy? Just restart?)
- Which of those fix actions can be made **idempotent and safely
  re-triggerable** (like `idempotent_rerun_order_events_job` in §3c) rather
  than a raw one-shot API call, so a retry doesn't cause a second failure
  mode?
- Which fix actions are safe to allow **fully autonomously** (no human
  approval) vs. which MUST stay behind the existing human-approval gate
  (currently: any step with `risk_level` MEDIUM/HIGH)?
- Should there be a generic **tool-execution engine** for the *approved*
  plan (see Gap #1) so that a plan step isn't just a free-text string but
  an actual `{tool_name, args}` pair that gets executed for real,
  regardless of which specific job/table it targets — replacing the
  current two-hardcoded-paths approach in `write_tools.py`?
- Beyond AWS-service coverage, are there **cross-cutting capabilities**
  (CloudTrail for "what changed", Cost Explorer for "will this fix blow
  the budget", VPC/SG tooling for "can this even reach that resource")
  that a real support engineer would reach for before proposing *any*
  fix, regardless of which specific service is involved?

This document is intentionally a snapshot of *what exists today*, not a
proposal — use it as the "current state" input for gap analysis.
