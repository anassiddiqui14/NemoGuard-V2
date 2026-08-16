# NemoGuard Enterprise Hardening & Productization Build Plan

**Status baseline:** 2026-08-16  
**Intended audience:** AI coding agent, engineering lead, architecture reviewer, security reviewer  
**Purpose:** Convert the current NemoGuard Pipeline Copilot alpha into a production-capable enterprise application without discarding the strong architecture that already exists.

---

# 0. READ THIS FIRST — EXECUTION RULES FOR THE CODING AGENT

This plan is intentionally prescriptive.

## Do not do the following unless explicitly called for in this document

- Do not perform another full UI redesign.
- Do not replace FastAPI.
- Do not replace PostgreSQL.
- Do not replace LangGraph.
- Do not replace Temporal.
- Do not add Kubernetes simply because this is an enterprise roadmap.
- Do not add more AI agents unless a specific functional gap requires one.
- Do not introduce arbitrary shell execution or unrestricted SQL execution.
- Do not grant models broad cloud credentials.
- Do not remove legacy code until all runtime dependencies are proven absent.
- Do not rewrite working subsystems merely for stylistic consistency.
- Do not allow the LLM to directly perform infrastructure mutation.
- Do not mark an incident RESOLVED based only on an action call returning success.
- Do not weaken deterministic safety policy for convenience.
- Do not merge new changes without automated tests once CI is introduced.

## Preserve and strengthen these existing architectural foundations

The current implementation already has the correct high-level building blocks:

1. PostgreSQL as the primary persistence layer.
2. Temporal workflow orchestration.
3. LangGraph-based investigation.
4. FastAPI API/control plane.
5. React/TypeScript frontend.
6. Structured multi-agent RCA with competing hypotheses.
7. Grounding Critic / independent safety review.
8. A governed Capability Gateway.
9. Deterministic capability compilation.
10. Risk-based execution policy.
11. Human approval.
12. Plan hashing.
13. Independent post-action verification.
14. Audit events and SSE.
15. LocalStack-backed real infrastructure testing.

The objective is to make those pieces **reliable, secure, observable, testable, tenant-safe, operationally supportable, and extensible**.

---

# 1. CURRENT VERIFIED BASELINE

The current product should be treated as a strong engineering alpha, not as a prototype.

## Current deployable services

- `postgres`
  - PostgreSQL 15
  - Current source of truth
- `temporal`
  - Temporal development server
  - NOT production-durable yet
- `api`
  - FastAPI REST + SSE + auth
- `temporal-worker`
  - Executes `IncidentLifecycleWorkflow`
- `frontend`
  - React 19 + Vite + TypeScript + Tailwind
- `simulator`
  - Scenario injection service
- `localstack`
  - Optional lab profile for AWS-compatible infrastructure testing

## Current operational workflow

```text
Webhook / Simulator
        |
        v
WatcherAgent
        |
        v
Correlation / Incident association
        |
        v
Temporal IncidentLifecycleWorkflow
        |
        v
LangGraph Investigation
        |
        +--> RCA Agent
        +--> Dependency / Impact Agent
        +--> Runbook Agent
        |
        v
Grounding Critic
        |
        v
Human Approval
        |
        v
Capability Gateway
        |
        v
Policy Check
        |
        v
Precondition Check
        |
        v
Execution
        |
        v
Independent Verification
        |
        +--> RESOLVED
        |
        +--> FAILED / ESCALATED
```

## Current strong points

- Multi-hypothesis root cause analysis exists.
- Supporting and contradicting evidence are modeled.
- Evidence carries authority levels.
- Grounding Critic has read-only tool access.
- Capability execution is real for a bounded set of actions.
- Capability policies are code-enforced.
- Policy configuration can make behavior stricter but not weaker.
- Plan hashes are recomputed and checked during approval.
- Execution-time policy re-check exists.
- LocalStack integration has demonstrated a real break -> remediate -> verify path.
- Frontend has evolved into a multi-route React application.
- Agent activity is increasingly driven by real SSE/audit events.

## Current high-risk gaps

1. Large uncommitted working tree.
2. No automated test suite.
3. No CI pipeline.
4. Temporal is running in dev mode.
5. State machine exists but is bypassed by raw status updates.
6. Deterministic correlator exists but is not the primary live correlation path.
7. Impact/Runbook reasoning ordering is suboptimal.
8. Feedback/rejection does not trigger a full re-investigation.
9. Authentication is incomplete on read endpoints and SSE.
10. Tenant/workspace columns are not enforced in queries.
11. Webhook payloads have weak validation/size control.
12. No rate limiting.
13. Capability action surface is still narrow.
14. Airflow/Datadog connectors are stubs.
15. Legacy/dead code remains in the live repository.
16. Observability tables are only partially populated.
17. Severity representation is inconsistent.

---

# 2. TARGET PRODUCT POSITIONING

Do not build NemoGuard as "a chatbot that reads logs."

Build it as:

> **A governed autonomous control plane for data-pipeline incident response.**

The core differentiator is not only AI root cause analysis.

It is:

> **AI reasoning converted into bounded, policy-governed, human-authorized operational actions that are independently verified before an incident is considered resolved.**

The product must earn trust in four dimensions:

1. **Correctness**
2. **Safety**
3. **Explainability**
4. **Operational reliability**

---

# 3. TARGET ENTERPRISE ARCHITECTURE

## 3.1 Logical architecture

```text
+-------------------------------------------------------------------+
|                         Operator Experience                        |
| React / TypeScript                                                 |
| Incidents | Intelligence | Agent Ops | Approvals | Admin | Audit   |
+----------------------------------+--------------------------------+
                                   |
                              REST / SSE
                                   |
+----------------------------------v--------------------------------+
|                         FastAPI Control Plane                       |
| Auth | RBAC | Tenancy | Incidents | Approval | Admin | Streaming   |
+-------------------+---------------------------+--------------------+
                    |                           |
                    |                           |
+-------------------v------------+   +----------v--------------------+
| Durable Workflow Layer         |   | AI Investigation Layer         |
| Temporal                       |   | LangGraph                       |
| Incident lifecycle             |   | RCA / Impact / Runbook /       |
| Approval wait                  |   | Grounding / Replanning         |
| Execution / Verification       |   | bounded reasoning only         |
+-------------------+------------+   +----------------+--------------+
                    |                                 |
                    +----------------+----------------+
                                     |
+------------------------------------v-------------------------------+
|                         Governed Tool Gateway                        |
| Typed Contracts | AuthZ | Policy | Risk | Audit | Idempotency       |
+----------------+------------------------------+---------------------+
                 |                              |
                 |                              |
+----------------v---------------+   +----------v---------------------+
| Read Connectors                |   | Action Capabilities             |
| Logs                           |   | Retry job                       |
| Metrics                        |   | Pause/resume                    |
| CMDB / lineage                 |   | Cleanup partial writes          |
| Deployment history             |   | Redrive                        |
| Runbooks                       |   | Rollback config                 |
+----------------+---------------+   +----------+---------------------+
                 |                              |
                 +---------------+--------------+
                                 |
+--------------------------------v------------------------------------+
| Customer Platforms / Managed Environments                            |
| AWS | Airflow | Databricks | Datadog | ServiceNow | Slack/Teams     |
+---------------------------------------------------------------------+

Supporting:
PostgreSQL | Object Storage | Secrets Manager | OpenTelemetry
Queue/Event Bus | Feature Flags | Model Provider Abstraction
```

## 3.2 Design boundary: deterministic control vs AI reasoning

### AI is allowed to

- Decide which diagnostic tools are useful.
- Generate and rank root cause hypotheses.
- Explain causal relationships.
- Request more evidence.
- Match or adapt approved runbooks.
- Draft recovery intent.
- Explain risk and uncertainty.
- Draft stakeholder communications.

### AI must NOT be authoritative for

- Whether an approval exists.
- Whether an operator has permission.
- The number of impacted assets.
- Current incident state.
- Whether a capability is allowed.
- Whether a capability executed successfully.
- Whether post-action verification passed.
- Whether an incident is resolved.
- SLA arithmetic.
- Tenant/workspace scope.
- Authorization decisions.
- Plan integrity.
- Policy decisions that can be encoded deterministically.

---

# 4. PRIORITY 0 — PROTECT THE CURRENT WORK

This must happen before substantive feature work.

## 4.1 Create a stable repository checkpoint

### Tasks

- Commit all currently working changes.
- Ensure newly created frontend/auth/capability files are tracked.
- Push to a remote repository.
- Create a release tag: `alpha-current-2026-08-16`.
- Create a working branch: `enterprise-hardening`.
- Record the exact Docker image versions.
- Record environment variables required to boot.
- Save migration version state.
- Save an example `.env.example`.
- Add a documented startup procedure.
- Capture the current successful LocalStack scenario.
- Capture the current successful approve/execute/verify flow.

### Acceptance criteria

- Fresh clone works on a clean machine.
- A developer can run database, Temporal, API, worker, frontend, simulator, and LocalStack lab.
- No undocumented local files are required.
- Git status is clean after setup.
- A release tag exists.

---

# 5. PRIORITY 1 — BUILD THE TEST SAFETY NET

This is the highest-leverage investment.

## 5.1 Backend unit tests

Create a formal `tests/` hierarchy.

```text
tests/
  unit/
    domain/
      test_state_machine.py
      test_correlator.py
      test_evidence_authority.py
      test_plan_hash.py
      test_severity.py
    capabilities/
      test_registry.py
      test_plan_compiler.py
      test_policy.py
      test_intent_mapper.py
      test_execution_engine.py
    auth/
      test_rbac.py
      test_tenant_scope.py
  integration/
    test_postgres_migrations.py
    test_api_auth.py
    test_incident_repository.py
    test_approval_api.py
    test_capability_execution.py
    test_audit_events.py
  e2e/
    test_schema_regression_golden_path.py
    test_verification_failure.py
    test_policy_block.py
    test_cross_tenant_access_denied.py
```

## 5.2 Mandatory unit tests

### State machine

Test every valid and invalid transition.

Examples of valid transitions:

```text
DETECTED -> INVESTIGATING
PLAN_READY -> AWAITING_APPROVAL
AWAITING_APPROVAL -> EXECUTING
EXECUTING -> VERIFYING
VERIFYING -> RESOLVED
```

Examples of invalid transitions:

```text
DETECTED -> RESOLVED
RESOLVED -> EXECUTING
FAILED -> RESOLVED without explicit reopen flow
```

### Plan hash

Test that:

- identical plan = identical hash
- changed action = different hash
- changed parameters = different hash
- changed order = different hash
- changed risk metadata changes hash when policy-relevant
- approval with stale hash fails

### Capability policy

Test:

- unknown capability fails closed
- invalid YAML fails closed
- config may make policy stricter
- config cannot make a high-risk code policy weaker
- execution-time policy check cannot be bypassed

### Intent mapping

Test all supported agent intent forms.

Unknown intent must produce a manual or blocked path, not arbitrary execution.

## 5.3 Integration tests

### Authentication

- unauthenticated mutations -> 401
- viewer trying admin endpoint -> 403
- wrong tenant -> 404 or 403 according to policy
- expired token -> 401
- malformed token -> 401

### Approval

- correct plan hash -> accepted
- stale plan hash -> 409
- wrong user role -> denied
- duplicate approval -> idempotent behavior
- plan changed after approval -> execution blocked

### Execution

- precondition failure -> no mutation
- execution failure -> verification not falsely passed
- verification failure -> incident not RESOLVED
- policy failure -> no mutation
- action retry uses idempotency key

## 5.4 End-to-end golden path

The test must drive the real public API, not call internal functions directly.

```text
1. Trigger a known scenario.
2. Wait for incident creation.
3. Wait for investigation completion.
4. Assert >=2 hypotheses exist.
5. Assert supporting evidence exists.
6. Assert contradicting evidence can be represented.
7. Assert recovery plan exists.
8. Assert safety critic result exists.
9. Approve the current plan hash.
10. Execute.
11. Wait for verification.
12. Assert capability results persisted.
13. Assert verification results persisted.
14. Assert final status == RESOLVED only if verification passed.
15. Assert audit trail reconstructs the entire sequence.
```

## 5.5 Negative end-to-end tests

### Unsafe plan

Expected:

```text
plan generated
-> safety policy rejects
-> no execution
-> NEEDS_REVIEW / BLOCKED
-> audit event persisted
```

### Verification failure

Expected:

```text
action executes
-> verification fails
-> incident remains unresolved
-> rollback/compensation attempted if configured
-> escalation audit event
```

---

# 6. PRIORITY 2 — ADD CI/CD IMMEDIATELY

Create CI before adding major features.

## 6.1 Pull request checks

Every PR must run:

### Python

- formatting check
- linting
- type checking
- unit tests
- integration tests

### Frontend

- TypeScript type checking
- lint
- unit/component tests
- production build

### Security

- secret scanning
- dependency vulnerability scanning
- container vulnerability scanning
- license scan if required
- SBOM generation

### Database

- migration lint/validation
- test migration from clean DB
- test migration from last release schema

## 6.2 Suggested merge gates

No merge if:

- unit tests fail
- integration tests fail
- TypeScript build fails
- migration fails
- secret scanner detects high-confidence credential
- high/critical vulnerability is introduced without an approved exception

---

# 7. PRIORITY 3 — ENFORCE THE STATE MACHINE

## 7.1 Problem

Current code changes incident status using raw SQL/update operations in multiple paths.

That allows:

- invalid transitions
- race conditions
- missing audit events
- state drift
- inconsistent UI events

## 7.2 Required architecture

Create a single incident transition service.

Example interface:

```python
class IncidentStateService:
    async def transition(
        self,
        *,
        incident_id: UUID,
        expected_from: IncidentState | set[IncidentState],
        to: IncidentState,
        actor: ActorIdentity,
        reason: str,
        metadata: dict | None = None,
    ) -> Incident:
        ...
```

## 7.3 Transition transaction

Within one DB transaction:

1. Lock incident row.
2. Load current status.
3. Validate expected status.
4. Validate state machine transition.
5. Update state.
6. Increment incident version.
7. Insert audit event.
8. Insert domain event/outbox event if used.
9. Commit.

## 7.4 Code rule

Prohibit direct writes to `incident.status` outside this service.

Enforce through repository design, code review, tests, and a grep/lint check if practical.

---

# 8. PRIORITY 4 — MAKE DETERMINISTIC CORRELATION PRIMARY

## 8.1 New correlation architecture

```text
Incoming alert
    |
    v
Canonical normalization
    |
    v
Deduplication
    |
    v
Deterministic candidate scoring
    |
    +--> High confidence -> attach/create automatically
    |
    +--> Medium confidence -> WatcherAgent adjudication
    |
    +--> Low confidence -> new incident candidate
```

## 8.2 Correlation signals

Support:

- same run ID
- same pipeline/workflow ID
- same batch/execution group
- temporal proximity
- identical/fuzzy error signature
- upstream/downstream topology
- common failed ancestor
- common deployment/change event
- same dataset/resource
- explicit blocked-by-parent relation
- same orchestration execution
- common infrastructure dependency

## 8.3 Correlation score contract

```json
{
  "candidate_incident_id": "INC-...",
  "score": 0.92,
  "signals": [
    {"type": "COMMON_UPSTREAM", "weight": 0.35},
    {"type": "TIME_PROXIMITY", "weight": 0.15},
    {"type": "ERROR_LINEAGE", "weight": 0.25},
    {"type": "SAME_DEPLOYMENT", "weight": 0.17}
  ],
  "decision": "AUTO_ATTACH"
}
```

## 8.4 Explainability

Persist correlation rationale.

The UI should be able to display:

> 11 alerts were consolidated because they share the same failed upstream job, occurred within 93 seconds, and are descendants of the same deployment change.

---

# 9. PRIORITY 5 — FIX THE INVESTIGATION GRAPH

## 9.1 Current problem

Impact and Runbook reasoning can occur without enough RCA context.

## 9.2 Target graph

```text
                 +--> Logs
                 |
Incident --> Evidence Collection --> RCA Hypotheses
                 |                       |
                 +--> Changes            |
                                         v
                           +-------------+-------------+
                           |                           |
                           v                           v
                     Impact Analysis             Runbook Match
                           |                           |
                           +-------------+-------------+
                                         |
                                         v
                                  Grounding Critic
                                         |
                                         v
                                   Recovery Plan
```

## 9.3 Investigation stages

### Stage 1 — Baseline evidence

Collect:

- incident alerts
- relevant logs
- recent deployments
- topology/CMDB
- run history
- basic business context

### Stage 2 — RCA

Produce:

- at least 2 plausible hypotheses when evidence permits
- confidence per hypothesis
- supporting evidence
- contradicting evidence
- missing evidence
- recommended next diagnostic actions

### Stage 3 — Evidence expansion

If top hypothesis confidence is below threshold:

- call additional tools
- collect evidence
- rerank

Bound the number of loops.

### Stage 4 — Impact

Use the primary failure/root candidates to calculate:

- impacted technical nodes
- impacted pipelines
- impacted datasets
- impacted products
- owners
- SLAs

The counts must be deterministic.

### Stage 5 — Runbook

Search based on incident class, suspected root cause, environment, component, failure type, and risk class.

### Stage 6 — Critic

Verify:

- evidence supports claims
- contradictory evidence was considered
- actions correspond to evidence
- unsafe steps are rejected
- write actions have required checks
- plan contains verification

---

# 10. PRIORITY 6 — REBUILD FEEDBACK / REJECTION FLOW

## 10.1 Current anti-pattern

Do not patch plan text in place after user rejection.

## 10.2 Correct behavior

Human feedback becomes authoritative incident evidence.

```text
User rejects plan
        |
        v
Persist feedback
        |
        v
Invalidate current plan
        |
        v
Create plan revision context
        |
        v
Re-enter LangGraph
        |
        v
Re-evaluate hypotheses
        |
        v
Recompute impact if needed
        |
        v
Re-evaluate runbook
        |
        v
Critic
        |
        v
New plan version + new hash
```

## 10.3 Plan versioning

Every plan must carry:

- `plan_id`
- `version`
- `parent_plan_id`
- `created_at`
- `created_by_agent_run_id`
- `feedback_reference`
- `hash`
- `status`

Old approved/rejected plans must remain immutable.

---

# 11. PRIORITY 7 — COMPLETE AUTHENTICATION & AUTHORIZATION

## 11.1 Immediate

Protect every API route unless intentionally public.

Must require auth:

- incident list
- incident detail
- evidence
- hypotheses
- alerts
- context endpoints
- audit events
- SSE event stream
- agent operations
- admin endpoints
- capability catalog
- recovery plans

## 11.2 Roles

Minimum roles:

```text
viewer
operator
commander
approver
admin
auditor
service
```

Suggested permissions:

### viewer

- read incidents
- read evidence
- read impact

### operator

- viewer +
- trigger triage
- add notes

### commander

- operator +
- propose/revise operational response
- execute approved medium-risk actions if policy allows

### approver

- approve/reject recovery plans

### admin

- manage users
- manage integrations
- manage policies
- manage capabilities
- manage models

### auditor

- read immutable audit view
- export audit records
- no operational mutation

## 11.3 Enterprise identity roadmap

Plan support for:

- OIDC
- SAML 2.0
- Microsoft Entra ID
- Okta
- SCIM provisioning

Local credentials may remain for development/self-hosted fallback.

---

# 12. PRIORITY 8 — ENFORCE MULTI-TENANCY

This is mandatory before external enterprise use.

## 12.1 Hierarchy

```text
Tenant
  |
  +--> Workspace
        |
        +--> Environment
              +--> production
              +--> staging
              +--> development
```

## 12.2 Tenant-scoped objects

At minimum:

- users
- memberships
- incidents
- alerts
- evidence
- hypotheses
- plans
- approvals
- actions
- tool calls
- integrations
- capabilities
- runbooks
- audit events
- model configuration
- policy configuration

## 12.3 Query rule

No repository method may query tenant resources without tenant context.

Bad:

```sql
SELECT * FROM incident WHERE id = $1;
```

Good:

```sql
SELECT *
FROM incident
WHERE id = $1
  AND tenant_id = $2
  AND workspace_id = $3;
```

## 12.4 PostgreSQL Row-Level Security

Consider RLS as defense in depth.

Application-level scoping remains required.

## 12.5 Cross-tenant tests

Add explicit tests proving:

- incident ID enumeration cannot cross tenant
- SSE cannot leak another tenant's events
- admin in tenant A cannot access tenant B
- connector credentials are tenant-scoped
- audit exports are tenant-scoped

---

# 13. PRIORITY 9 — HARDEN WEBHOOK INGESTION

## 13.1 Canonical schema

Introduce a versioned canonical alert envelope.

```json
{
  "schema_version": "1.0",
  "event_id": "...",
  "source": "cloudwatch",
  "source_account": "...",
  "workspace_id": "...",
  "event_type": "JOB_FAILED",
  "resource": {
    "type": "glue_job",
    "id": "..."
  },
  "occurred_at": "...",
  "severity": "ERROR",
  "message": "...",
  "attributes": {}
}
```

## 13.2 Validation

Enforce:

- maximum payload size
- required schema
- supported content type
- timestamp bounds
- source allowlist where configured
- field length limits
- nested object depth limits

## 13.3 Authentication

Support integration-specific auth:

- HMAC signatures
- API keys stored hashed
- mTLS for high-assurance customers
- OAuth where appropriate

## 13.4 Rate limiting

Limit by tenant, integration, source IP, and endpoint.

Use token bucket or sliding window.

## 13.5 Replay protection

Use event IDs, timestamps, signature validation, and deduplication cache/table.

---

# 14. PRIORITY 10 — PRODUCTION TEMPORAL

## 14.1 Replace dev server

Use either Temporal Cloud or production self-hosted Temporal.

## 14.2 Required production controls

- persistent Temporal database
- TLS
- authenticated connections
- namespaces
- namespace isolation
- worker identity
- task queues
- worker versioning
- deployment compatibility
- retention configuration
- monitoring
- backup strategy if self-hosted

## 14.3 Workflow signals

Approval, rejection, feedback, cancel, and escalation should be workflow signals.

Avoid synchronous side channels that mutate lifecycle state independently.

## 14.4 Workflow behavior

Support:

- approval timeout
- escalation timeout
- cancellation
- revision signal
- plan invalidation
- execution retry
- verification retry
- compensation/rollback
- manual takeover

## 14.5 Durability test

Test:

1. Incident reaches `AWAITING_APPROVAL`.
2. Kill API.
3. Kill worker.
4. Restart.
5. Submit approval.
6. Workflow resumes.
7. Execution occurs once.
8. Verification completes.

---

# 15. PRIORITY 11 — OBSERVABILITY

Use OpenTelemetry across all services.

## 15.1 Trace hierarchy

One incident should be traceable across:

```text
incident_id
  |
  +--> temporal_workflow_id
        |
        +--> langgraph_run_id
              |
              +--> agent_run_id
                    |
                    +--> tool_call_id
        |
        +--> capability_execution_id
              |
              +--> verification_id
```

## 15.2 Required telemetry

### API

- request count
- error rate
- p50/p95/p99 latency
- auth failures
- tenant-specific request volume

### Agents

- model latency
- tool calls per investigation
- tool failure rate
- token usage
- structured-output failures
- investigation loops
- hypothesis count
- critic failure rate

### Capability execution

- capability count
- risk distribution
- approval time
- precondition failure
- execution failure
- verification failure
- rollback count

### Temporal

- open workflows
- stuck workflows
- activity failures
- signal latency
- task queue backlog

### Product

- time to first hypothesis
- time to plan
- time awaiting human approval
- time to execute
- time to verify
- MTTR
- percentage resolved automatically/assisted
- operator rejection rate

## 15.3 Structured logging

Every log should carry as applicable:

- request_id
- trace_id
- tenant_id
- workspace_id
- incident_id
- workflow_id
- agent_run_id
- tool_call_id
- capability_execution_id

Never log secrets.

---

# 16. PRIORITY 12 — EXPAND THE CAPABILITY GATEWAY SAFELY

The Capability Gateway is the product's most important safety layer.

## 16.1 Capability contract

Every action capability should define:

```text
capability_id
version
description
target_type
risk
autonomy
input_schema
required_permissions
precondition_check
dry_run
execute
verify
rollback_or_compensate
timeout
idempotency_strategy
audit_classification
```

## 16.2 Required lifecycle

```text
Agent produces ActionIntent
        |
        v
Deterministic Plan Compiler
        |
        v
Capability lookup
        |
        v
Authorization
        |
        v
Policy
        |
        v
Preconditions
        |
        v
Dry Run if required
        |
        v
Human Approval if required
        |
        v
Execution-time policy recheck
        |
        v
Execute
        |
        v
Independent Verify
        |
        +--> Passed -> continue
        |
        +--> Failed -> rollback/escalate
```

## 16.3 Suggested capability expansion order

### Data integrity

1. check schema
2. check row count
3. check duplicate partition
4. check partial write
5. check data freshness
6. validate expected files

### Pipeline orchestration

1. retry job
2. cancel job
3. pause schedule
4. resume schedule
5. rerun failed task
6. rerun from checkpoint

### AWS

1. Glue start job run
2. Glue stop job run
3. Step Functions redrive/retry
4. SQS DLQ redrive
5. Lambda alias rollback
6. ECS service restart

Only add a capability after policy classification, deterministic tests, failure-mode tests, idempotency test, independent verification, and audit event coverage.

---

# 17. PRIORITY 13 — REAL CONNECTORS

Do not build ten partial integrations.

Build one complete production-quality integration ecosystem first.

## Recommended first target

AWS-native data operations:

```text
CloudWatch
  |
  v
Glue
  |
  +--> CloudWatch Logs
  +--> S3
  +--> Step Functions
  |
  v
NemoGuard
  |
  v
Approved Glue/Step Functions Capability
  |
  v
Verification against S3/job state
```

## Connector interface

Each connector should implement:

```python
class Connector(Protocol):
    async def health_check(...)
    async def discover_resources(...)
    async def read_events(...)
    async def query_context(...)
```

Action behavior should remain behind the Capability Gateway, not the connector itself.

## Connector admin metadata

Store:

- integration ID
- tenant/workspace
- type
- environment
- endpoint/account
- status
- last success
- last failure
- credential reference
- permissions granted
- permissions required
- version
- configuration
- health

---

# 18. PRIORITY 14 — RUNBOOK GOVERNANCE

Runbooks must be controlled enterprise artifacts.

## 18.1 Runbook schema

```text
runbook_id
version
title
service
component
failure_type
environment
owner
status
approved_by
approved_at
valid_from
expires_at
risk_class
required_evidence
allowed_capabilities
preconditions
steps
verification
rollback
tags
```

## 18.2 Lifecycle

```text
DRAFT
-> REVIEW
-> APPROVED
-> ACTIVE
-> DEPRECATED
-> RETIRED
```

## 18.3 Agent behavior

The agent may:

- identify a matching runbook
- explain why it matches
- adapt parameter values
- skip irrelevant optional steps

The agent may not:

- silently convert a prohibited capability into an allowed one
- ignore runbook expiration
- present an unapproved runbook as approved
- modify the source runbook during an incident

## 18.4 UI trust statement

Show:

```text
Based on:
RB-GLUE-017 v4
Approved by: Data Platform Engineering
Approved on: 2026-07-14
Environment: Production
```

---

# 19. PRIORITY 15 — AUDITABILITY

The audit trail must allow full reconstruction of every material incident decision.

## 19.1 Audit event principles

- append-only
- immutable in normal application paths
- tenant scoped
- timestamped
- actor identified
- correlation IDs
- event schema version
- before/after values for state changes where safe
- no secrets

## 19.2 Events to capture

### Ingestion

- ALERT_RECEIVED
- ALERT_REJECTED
- ALERT_DEDUPLICATED

### Correlation

- CORRELATION_CANDIDATE_EVALUATED
- ALERT_ATTACHED_TO_INCIDENT
- INCIDENT_CREATED

### Investigation

- INVESTIGATION_STARTED
- TOOL_CALLED
- TOOL_COMPLETED
- TOOL_FAILED
- HYPOTHESIS_CREATED
- HYPOTHESIS_RERANKED
- EVIDENCE_ADDED
- CRITIC_COMPLETED

### Plan

- PLAN_CREATED
- PLAN_REVISED
- PLAN_INVALIDATED
- PLAN_HASHED

### Approval

- APPROVAL_REQUESTED
- PLAN_APPROVED
- PLAN_REJECTED
- APPROVAL_EXPIRED

### Execution

- CAPABILITY_POLICY_CHECKED
- PRECONDITION_CHECKED
- ACTION_EXECUTION_STARTED
- ACTION_EXECUTION_COMPLETED
- ACTION_EXECUTION_FAILED
- VERIFICATION_STARTED
- VERIFICATION_PASSED
- VERIFICATION_FAILED
- ROLLBACK_STARTED
- ROLLBACK_COMPLETED

### Incident

- INCIDENT_STATE_CHANGED
- INCIDENT_ESCALATED
- INCIDENT_RESOLVED
- INCIDENT_REOPENED

## 19.3 AI audit record

For every material LLM decision persist:

- model provider
- model ID
- model version if available
- prompt template/version
- tool schema version
- input evidence references
- structured output
- validation result
- latency
- token usage
- cost estimate where available

Do not store hidden chain-of-thought. Store observable decision outputs and evidence references.

---

# 20. PRIORITY 16 — ADMINISTRATION CONSOLE

Create a serious enterprise administration area.

## 20.1 Users and access

Pages:

- users
- groups
- roles
- workspace memberships
- service accounts

Actions:

- invite
- disable
- assign role
- remove access
- review last login
- review last privilege change

## 20.2 Integrations

Display:

```text
Integration
Environment
Status
Last successful read
Last failure
Permissions
Credential expiry
Version
```

Actions:

- configure
- test connection
- rotate credential
- disable
- view connector logs

## 20.3 Capability policy

Admin must be able to inspect:

```text
Capability
Risk
Autonomy
Enabled?
Required role
Requires approval?
Requires dry run?
Allowed environment?
```

Policy changes must be audited, versioned, deterministic, and must not retroactively mutate an approved plan.

## 20.4 Model administration

Allow configuration of:

- model for RCA
- model for critic
- fallback model
- timeout
- max tokens
- provider
- residency class
- monthly budget
- per-tenant limits

## 20.5 Runbook governance

Admins should manage owners, review dates, approval, expiration, allowed capabilities, and environment scope.

---

# 21. PRIORITY 17 — MODEL PROVIDER ABSTRACTION

Avoid vendor lock-in in the application core.

## 21.1 Interface

```python
class StructuredReasoningProvider(Protocol):
    async def generate(
        self,
        *,
        messages: list[Message],
        output_model: type[T],
        tools: list[ToolSchema],
        timeout_seconds: int,
        metadata: dict,
    ) -> T:
        ...
```

## 21.2 Providers

Support over time:

- NVIDIA NIM
- OpenAI
- Anthropic
- local/open model
- customer-managed endpoint

## 21.3 Routing factors

Select based on:

- tenant policy
- environment
- data sensitivity
- residency
- latency
- quality
- cost
- availability
- output reliability

## 21.4 Fallback

Fallback must not silently violate data residency or customer policy.

---

# 22. PRIORITY 18 — SECURITY HARDENING

## 22.1 Secrets

Use a secrets manager in production.

Do not:

- store connector secrets in plaintext DB
- expose secrets to the LLM
- log secrets
- return secrets through API payloads

## 22.2 Least privilege

Each integration credential should expose only required actions.

Prefer separate identities for diagnostic reads, low-risk actions, and elevated actions.

## 22.3 Prompt injection defense

Treat all retrieved content as untrusted.

Logs, tickets, runbooks, comments, and alert text can contain malicious instructions.

The agent system must distinguish trusted system instructions from external evidence.

Retrieved text must never be allowed to redefine policy, tool permissions, approval requirements, tenant identity, or system prompt.

## 22.4 Tool input validation

All tools require:

- typed inputs
- bounds
- allowlists
- resource ownership check
- tenant scope
- environment scope

## 22.5 SSRF

Connector endpoints must be validated.

Block localhost, metadata service addresses, internal ranges unless explicitly approved, and arbitrary user-supplied URL fetches.

## 22.6 Denial-of-wallet

Control:

- max model calls per investigation
- max tool calls
- max investigation loops
- max context
- rate limits
- tenant budgets

---

# 23. PRIORITY 19 — USER EXPERIENCE

Do not redesign the application from scratch. Improve task completion and trust.

## 23.1 Operator home

Show:

- active incidents
- severity
- status
- SLA risk
- current AI stage
- approval waiting
- recovery in progress

## 23.2 Incident workspace

Required sections:

### Situation

- incident title
- severity
- environment
- time detected
- owner
- lifecycle state

### RCA

- primary hypothesis
- confidence
- alternative hypotheses
- supporting evidence
- contradicting evidence

### Impact

- technical impact
- business impact
- SLA
- owners

### Investigation activity

- tool calls
- agent stages
- evidence collection
- errors

### Recovery

- plan
- risk
- preconditions
- actions
- verification
- rollback

### Approval

- exact plan version
- plan hash
- expected effect
- risk
- approver

### Audit

- immutable event timeline

## 23.3 Error states

Never show ambiguous placeholders.

Bad:

> No plan yet.

Better:

> Investigation failed during structured response validation. Retry or view technical details.

## 23.4 Trust signals

Surface:

- evidence IDs
- approved runbook version
- policy version
- model used
- last verification result
- whether an action was automatic or human-approved

---

# 24. PRIORITY 20 — CODEBASE CLEANUP

Do this after test coverage exists.

## 24.1 Candidate legacy paths

Review:

- legacy SQLite store
- Streamlit UI
- obsolete MCP server
- legacy read tools
- older tool registries
- Commander fallback path
- vendored unrelated repositories

## 24.2 Removal rule

A file may be deleted only if:

- no import references
- no runtime references
- no test dependency
- no deployment dependency
- replacement path has tests

## 24.3 Preferred strategy

Create `docs/architecture/runtime-path.md` documenting one canonical execution path.

The repository should make it obvious what is production code and what is experimental.

---

# 25. PRIORITY 21 — FIX DATA MODEL INCONSISTENCIES

## 25.1 Severity

Use an enum internally:

```text
SEV_1
SEV_2
SEV_3
SEV_4
```

Store canonical values consistently.

Render:

```text
SEV-1
SEV-2
SEV-3
SEV-4
```

via a display formatter.

Create migration if necessary.

## 25.2 Status

All state values should use a single enum. No arbitrary strings.

## 25.3 Timestamps

Use UTC in storage. UI renders local time. Store timezone-aware timestamps.

## 25.4 IDs

Use standard IDs consistently:

- UUID or ULID for database identity
- human-readable short display IDs separately

---

# 26. PRIORITY 22 — ERROR TAXONOMY

Introduce stable error codes.

Examples:

```text
AUTH_001 INVALID_TOKEN
AUTH_002 INSUFFICIENT_ROLE
TENANT_001 TENANT_SCOPE_VIOLATION
INCIDENT_001 INVALID_STATE_TRANSITION
PLAN_001 STALE_PLAN_HASH
PLAN_002 PLAN_INVALIDATED
CAP_001 UNKNOWN_CAPABILITY
CAP_002 PRECONDITION_FAILED
CAP_003 POLICY_BLOCKED
CAP_004 EXECUTION_FAILED
CAP_005 VERIFICATION_FAILED
MODEL_001 STRUCTURED_OUTPUT_INVALID
MODEL_002 PROVIDER_TIMEOUT
CONNECTOR_001 AUTH_FAILED
CONNECTOR_002 RATE_LIMITED
CONNECTOR_003 UNAVAILABLE
WORKFLOW_001 TEMPORAL_UNAVAILABLE
```

API responses should include:

```json
{
  "error": {
    "code": "PLAN_001",
    "message": "The recovery plan changed after it was reviewed.",
    "request_id": "REQ-...",
    "retryable": false
  }
}
```

---

# 27. PRIORITY 23 — RESILIENCE

## 27.1 Timeouts

Every external call must have a timeout:

- model
- connector
- capability
- DB query
- workflow activity

## 27.2 Retries

Retry only safe failures.

Use exponential backoff, jitter, and max attempt count.

Do not blindly retry writes.

## 27.3 Circuit breakers

Add for model providers, connectors, and ticketing systems.

## 27.4 Idempotency

Mutation APIs must support idempotency keys.

Capability execution must be idempotent or explicitly compensate.

## 27.5 Queueing

If ingestion grows:

- decouple webhook acceptance from processing
- acknowledge after durable event persistence
- process asynchronously

---

# 28. PRIORITY 24 — PERFORMANCE & COST OPTIMIZATION

Optimize only after telemetry exists.

## 28.1 Database

Add indexes based on observed queries.

Likely:

- `(tenant_id, workspace_id, status, created_at)`
- `(incident_id, created_at)` for events
- `(incident_id, rank)` for hypotheses
- `(incident_id, authority)` for evidence
- `(plan_id, sequence)` for actions

## 28.2 Model

Reduce cost through:

- deterministic correlation first
- small model for Watcher
- larger model only for difficult RCA
- cache stable runbook embeddings/search
- bound tool loops
- avoid sending full raw logs when summarized evidence is enough
- retain source references

## 28.3 Investigation context

Prefer:

```text
source record
-> deterministic extraction
-> bounded evidence object
-> model
```

rather than sending thousands of raw log lines.

## 28.4 Frontend

- single SSE connection per incident
- avoid polling where SSE already provides updates
- lazy-load heavy visualizations
- paginate audit history
- virtualize large lists

---

# 29. PRIORITY 25 — PRODUCT METRICS

Track business value.

## Core metrics

### Detection and correlation

- alerts per incident
- deduplication rate
- correlation precision
- correlation recall

### Investigation

- time to first useful hypothesis
- RCA top-1 accuracy
- RCA top-3 accuracy
- evidence citation coverage
- critic disagreement rate

### Recovery

- time to recovery plan
- approval latency
- execution success
- verification success
- rollback frequency

### Business

- MTTR improvement
- incidents resolved without escalation
- operator time saved
- alert reduction
- recurrence rate
- prevented SLA breaches

### AI economics

- model cost per incident
- calls per incident
- tokens per incident
- model failure rate

---

# 30. PRIORITY 26 — PILOT INTEGRATION

Once the application is stable, perform a real non-production pilot.

## Recommended scope

One platform family.

Example AWS data pipeline pilot:

- CloudWatch
- Glue
- S3
- Step Functions

## Pilot use case

```text
Glue job fails
  |
  v
CloudWatch alert enters NemoGuard
  |
  v
Logs + recent changes gathered
  |
  v
Pipeline / Step Functions impact calculated
  |
  v
Approved runbook selected
  |
  v
Human approves retry/rollback
  |
  v
Glue action executed
  |
  v
S3 + Glue run independently verified
```

## Pilot exit criteria

- at least 20 incident scenarios
- known root cause labels
- measured RCA accuracy
- no policy bypass
- complete audit reconstruction
- zero cross-tenant data leaks
- workflow restart durability tested
- at least one real safe mutation in non-production

---

# 31. ADMINISTRATION ROADMAP

## Phase A

- capability catalog
- policy viewer
- integration health
- users/roles
- workspace selector

## Phase B

- runbook governance
- model configuration
- tenant policies
- approval matrix
- audit export

## Phase C

- SSO/SCIM
- service accounts
- custom roles
- data retention
- legal hold
- regional configuration

---

# 32. AUDITOR EXPERIENCE

Create a dedicated auditor view.

Auditor should be able to select an incident and reconstruct:

```text
08:43:01 Alert received
08:43:02 Alert attached to INC-1007
08:43:03 Investigation started
08:43:05 Logs retrieved
08:43:07 Hypothesis H1 created
08:43:08 Hypothesis H2 created
08:43:11 Critic approved findings
08:43:13 Recovery plan v2 created
08:45:40 Approved by user@example.com
08:45:42 Plan hash validated
08:45:43 Capability policy passed
08:45:44 Preconditions passed
08:45:47 Action executed
08:45:51 Verification passed
08:45:52 Incident resolved
```

Auditor should be able to inspect evidence, model/version, prompt version, tool calls, plan, approval, policy version, action result, and verification.

---

# 33. SUPPORT & OPERATIONS EXPERIENCE

Enterprise productization requires operating NemoGuard itself.

## Support tooling

Provide:

- health dashboard
- connector status
- worker status
- Temporal status
- model provider status
- DB status
- event backlog
- failed workflow list
- failed capability list

## Support bundle

Generate a redacted support package containing:

- service versions
- configuration summary
- recent errors
- workflow ID
- trace IDs
- connector health
- migration version

Do not include secrets.

---

# 34. RELEASE ENGINEERING

## Environment strategy

```text
local
development
integration
staging
production
```

## Required differences

Production must:

- disable mock login
- disable unrestricted simulator access
- disable wildcard CORS
- require TLS
- require authentication
- use durable Temporal
- use managed secrets
- enforce tenant scope
- enable production observability

## Release artifact

Each release should produce:

- backend container
- frontend container/static artifact
- Temporal worker container
- migration package
- SBOM
- build provenance
- release notes

---

# 35. FIRST 6 WEEKS — EXECUTION PLAN

# Week 1 — Stabilize the engineering baseline

## Tasks

- checkpoint all current changes
- push remote backup
- create release tag
- fix severity inconsistency
- wire state machine
- remove direct status writes
- create test scaffolding
- create clean-clone setup documentation

## Exit gate

```text
fresh clone
-> documented environment setup
-> docker compose up
-> migrations complete
-> frontend loads
-> simulator works
-> golden scenario can be executed manually
```

---

# Week 2 — Tests, CI, security

## Tasks

- unit tests for critical domain logic
- plan hash tests
- capability policy tests
- state machine tests
- integration tests
- E2E golden path
- negative verification test
- CI pipeline
- secret scan
- dependency scan
- protect read APIs
- protect SSE
- webhook validation
- rate limiting

## Exit gate

No critical workflow change can merge without automated regression coverage.

---

# Week 3 — Investigation correctness

## Tasks

- deterministic correlator becomes primary
- Watcher only handles ambiguity
- RCA before impact/runbook
- bounded additional evidence loop
- remove generic hardcoded fallback plan
- feedback triggers reinvestigation
- audit tool calls
- populate `agent_run`, `agent_step`, `tool_call`

## Exit gate

Run a fixed evaluation suite of >=10 scenarios.

For each, store:

- ground truth cause
- expected impact
- correct runbook
- unsafe actions
- expected verification

---

# Week 4 — Workflow durability

## Tasks

- deploy production Temporal or Temporal Cloud staging
- signals for approve/reject/revise
- timeouts
- retries
- worker restart testing
- API restart testing
- cancellation
- escalation
- workflow versioning strategy

## Exit gate

An incident waiting for approval survives full application restart and resumes correctly.

---

# Week 5 — Real integration

## Tasks

Select one ecosystem.

Recommended AWS:

- CloudWatch event ingestion
- Glue logs/status
- S3 verification
- Step Functions context
- one or two real action capabilities
- least-privilege IAM

## Exit gate

NemoGuard diagnoses and safely remediates a real non-production incident with independent verification.

---

# Week 6 — Pilot readiness

## Tasks

- tenant/workspace enforcement
- basic admin console
- integration health
- runbook governance
- audit export
- user documentation
- operator onboarding
- architecture/security docs
- support procedure

## Exit gate

A second engineer can deploy and operate the product without the original author.

---

# 36. 90-DAY ROADMAP

## Days 1-30 — Trust

Focus on tests, CI, state correctness, authentication, tenant isolation, deterministic correlation, and workflow durability.

Do not chase breadth.

## Days 31-60 — Operational usefulness

Focus on first real connector, 10-20 additional diagnostic tools, 5-10 safe action capabilities, runbook governance, observability, and operator UX.

## Days 61-90 — Enterprise readiness

Focus on admin controls, SSO groundwork, audit export, retention controls, deployment packaging, pilot, performance, security review, and documentation.

---

# 37. DEFINITION OF ALPHA 1

Call the next release:

> **NemoGuard Alpha 1 — Governed Autonomous Incident Response**

Alpha 1 must support:

```text
Alert ingestion
-> deterministic correlation
-> one incident
-> multi-agent evidence-grounded RCA
-> technical/business impact
-> approved runbook matching
-> governed recovery plan
-> human approval
-> deterministic capability execution
-> independent verification
-> immutable audit history
```

## Alpha 1 hard gates

- [ ] Clean repository checkpoint exists
- [ ] CI is mandatory
- [ ] Core unit tests pass
- [ ] E2E golden path passes
- [ ] E2E failure path passes
- [ ] Unauthorized execution is blocked
- [ ] Cross-tenant access tests pass
- [ ] State machine is enforced
- [ ] No direct status updates
- [ ] Temporal is durable in staging
- [ ] Read APIs require auth
- [ ] SSE requires auth
- [ ] Webhook validation exists
- [ ] Rate limiting exists
- [ ] Plan hash verification is enforced
- [ ] Capability policy re-checks at execution
- [ ] Independent verification is required
- [ ] Audit trail reconstructs the incident
- [ ] At least one real non-production integration exists

---

# 38. DEFINITION OF BETA

Beta should add:

- production-like Temporal
- SSO/OIDC
- stronger admin
- runbook lifecycle
- 2-3 production connectors
- 10+ action capabilities
- tenant isolation
- operational telemetry
- backup/recovery
- security test suite
- pilot customer deployment

---

# 39. DO NOT CALL IT PRODUCTION-READY UNTIL

## Identity

- SSO or enterprise-approved auth
- tenant isolation tested
- no open sensitive endpoints
- least privilege

## Reliability

- durable workflow engine
- restart recovery tested
- DB backup
- disaster recovery plan
- idempotent actions

## Safety

- deterministic capability policy
- human approval
- plan integrity
- preconditions
- independent verification
- rollback/compensation

## Audit

- complete append-only event history
- actor attribution
- model/tool provenance
- export

## Operations

- dashboards
- alerts
- runbooks
- support procedures
- on-call ownership

## Engineering

- CI
- automated tests
- migration discipline
- release process
- vulnerability management

---

# 40. FILE-LEVEL IMPLEMENTATION WORKSTREAMS

The coding agent should inspect the repository before changing names, but the following areas are expected to be modified.

## `src/domain/state_machine.py`

- make authoritative
- add full test coverage
- expose transition validator

## `src/domain/orchestrator.py`

- remove raw incident state writes
- invoke transition service
- ensure workflow actions are idempotent
- improve audit output

## `src/domain/correlator.py`

- make live primary path
- add topology signals
- persist correlation evidence
- add thresholds

## `src/domain/agents/langgraph_investigator.py`

- reorder graph
- RCA before impact/runbook where needed
- bounded evidence expansion
- improved plan revision
- structured output validation

## `src/domain/agents/watcher_agent.py`

- change role from primary correlator to ambiguity adjudicator

## `src/capabilities/`

- strengthen metadata
- add dry-run abstraction
- add rollback/compensation
- expand tests
- expand capability set incrementally

## `src/api/auth.py`

- complete real auth
- enforce tenant context
- prepare for OIDC adapter

## `src/api/main.py`

- secure all reads
- secure SSE
- input validation
- rate limiting hooks
- consistent errors
- tenant scoping

## `src/store/postgres_database.py`

- tenant-aware repository methods
- transaction-safe state transitions
- indexes
- remove direct state mutation helpers

## `frontend/`

- preserve current structure
- add clear auth/error states
- admin shell
- audit experience
- connector health
- trust/provenance surfaces

## `migrations/`

Expected additions:

- tenant/workspace enforcement fields/indexes if incomplete
- state/version columns
- runbook governance
- integration metadata
- policy version metadata
- audit metadata
- idempotency keys

## `config/`

- version capability policy
- environment-specific policy
- validate config schema

## `localstack_lab/`

- expand negative scenarios
- use in CI where feasible
- retain as integration-lab infrastructure

---

# 41. REQUIRED EVALUATION DATASET

Create a repeatable scenario suite.

At minimum:

1. Schema regression
2. Partial write
3. Missing source file
4. Late source file
5. OOM job failure
6. Credential failure
7. Rate limit
8. Step Functions downstream block
9. Data quality threshold failure
10. Duplicate partition
11. Deployment regression
12. Unrelated simultaneous incidents
13. Noisy duplicate alerts
14. False-positive alert
15. Unsafe rerun scenario

Each scenario must define:

```text
scenario_id
ground_truth_root_cause
expected_alert_cluster
expected_primary_resource
expected_impact
correct_runbook
allowed_actions
unsafe_actions
verification_expectations
```

---

# 42. QUALITY METRICS FOR THE EVALUATION SUITE

Track:

- correlation precision
- correlation recall
- RCA top-1
- RCA top-3
- evidence citation coverage
- blast radius recall
- runbook selection accuracy
- unsafe action prevention
- verification accuracy
- false resolution rate
- mean investigation time
- model cost

A critical target:

> **False resolution rate must approach zero.**

It is safer to escalate than falsely claim recovery.

---

# 43. GOVERNANCE PRINCIPLE

NemoGuard should never "learn" production policy silently.

Operator feedback can improve retrieval ranking, hypothesis calibration, runbook recommendations, and correlation heuristics.

But changes to capability risk, approval policy, allowed actions, runbook approval, and automation scope must be versioned and reviewed.

---

# 44. PRODUCT PRINCIPLE

Every feature must improve at least one of:

1. Mean time to understand
2. Mean time to safe action
3. Mean time to verified recovery
4. Operator trust
5. Auditability
6. Operational safety

If a feature does none of these, deprioritize it.

---

# 45. FINAL IMPLEMENTATION ORDER

The coding agent should use this order unless blocked.

## Immediate

1. Commit/checkpoint current work.
2. Fix severity convention.
3. Create test framework.
4. Build CI.
5. Wire state machine.

## Next

6. Secure read/SSE endpoints.
7. Add rate limiting/webhook validation.
8. Enforce tenant scoping.
9. Make deterministic correlator primary.
10. Correct LangGraph dependencies.
11. Rebuild feedback/revision.

## Then

12. Production Temporal.
13. Full OpenTelemetry.
14. Expand Capability Gateway.
15. Real connector.
16. Runbook governance.
17. Administration console.
18. Audit exports.

## Later

19. SSO/SCIM.
20. Multiple connector ecosystems.
21. Advanced analytics.
22. Advanced automated remediation.

---

# 46. FINAL ARCHITECTURE PRINCIPLE

The final system should preserve this separation:

```text
AI says:
"I believe this is the cause, here is my evidence, and here is the action I recommend."

Deterministic platform says:
"You are permitted to recommend that action.
The parameters are valid.
The action exists.
The user is authorized.
The policy permits it.
The approval is valid.
The plan has not changed.
The preconditions are satisfied."

Capability executes.

Independent verifier says:
"The system has actually recovered."

Only then:

INCIDENT = RESOLVED
```

This is the core architectural contract of NemoGuard.

---

# 47. CODING AGENT COMPLETION REPORT FORMAT

After each work package, the coding agent must report:

```text
WORK PACKAGE:
STATUS:

FILES CHANGED:

MIGRATIONS:

TESTS ADDED:

TEST RESULTS:

SECURITY IMPACT:

BACKWARD COMPATIBILITY:

KNOWN LIMITATIONS:

MANUAL VALIDATION:

ROLLBACK PROCEDURE:

NEXT RECOMMENDED PACKAGE:
```

Do not accept "implemented" without test evidence.

---

# 48. FIRST WORK PACKAGE TO START NOW

## WP-001 — Engineering Baseline & State Integrity

### Objectives

- protect current work
- introduce automated tests
- normalize severity
- make incident state transitions authoritative

### Tasks

1. Commit/checkpoint working tree.
2. Add test framework.
3. Add state machine unit tests.
4. Add severity unit tests.
5. Normalize severity handling.
6. Create `IncidentStateService`.
7. Replace direct incident status writes in active runtime paths.
8. Add transition audit events.
9. Add an integration test proving invalid transitions are rejected.
10. Run the existing LocalStack golden path.

### Acceptance criteria

- all tests pass
- no active path directly updates incident status
- severity KPI bug is fixed
- every state change has an audit event
- LocalStack scenario still resolves correctly
- repository is clean

Once WP-001 passes, proceed to WP-002:

> **WP-002 — CI, Authentication Completion, Webhook Hardening & Tenant Scope**

Then WP-003:

> **WP-003 — Correlation and Investigation Correctness**

Then WP-004:

> **WP-004 — Durable Temporal and Replanning**

Then WP-005:

> **WP-005 — Real AWS Pilot Integration and Expanded Capabilities**

---

# END OF BUILD PLAN
