# NemoGuard — Next-Phase Engineering Execution Plan

**Baseline:** APP_STATUS_REPORT_2026-08-21  
**Branch at baseline:** `enterprise-hardening` @ `9f31ad2`  
**Audience:** Coding agent / engineering lead / architecture reviewer  
**Purpose:** Define exactly what to do next now that NemoGuard has moved beyond POC status into a hardened engineering alpha.

---

# 1. Executive direction

NemoGuard is no longer primarily an AI demo. The current application already has PostgreSQL, Temporal, LangGraph, FastAPI, React/TypeScript, multi-hypothesis RCA, an Impact Agent, Runbook Agent, read-only Grounding Critic, real human approval through Temporal signals, a governed Capability Gateway, code-enforced policy, preconditions, independent verification, multi-tenancy, RBAC, hardened webhook ingestion, CI, substantial automated tests, and LocalStack-backed infrastructure testing.

The next phase must therefore focus on:

1. Durability.
2. Execution safety.
3. Observability.
4. Business-impact quality.
5. Real integration depth.
6. Evaluation quality.
7. Codebase clarity.
8. Pilot readiness.

Do **not** spend the next phase adding superficial AI features.

The product should mature around this contract:

```text
AI reasons and recommends.
Deterministic platform validates and authorizes.
Governed capability executes.
Independent verifier proves the outcome.
Only then can the incident be resolved.
```

That is the core architectural promise of NemoGuard.

---

# 2. Current verified baseline

Treat the following as existing, working foundations unless repository inspection proves otherwise.

## 2.1 Verified end-to-end lifecycle

```text
Webhook / Simulator
        |
        v
WatcherAgent
        |
        v
CorrelatorEngine
        |
        v
Temporal IncidentLifecycleWorkflow
        |
        v
LangGraph Investigation
        |
        +--> RCA Agent
        +--> Dependency Agent
        +--> Runbook Agent
        |
        v
Grounding Critic
        |
        v
PLAN_READY
        |
        v
AWAITING_APPROVAL
        |
        +--> timeout -> escalation
        +--> cancel -> CANCELLED
        +--> reject -> INVESTIGATING
        +--> approve -> EXECUTING
                            |
                            v
                    Capability Gateway
                            |
                            v
                        compile
                            |
                            v
                     policy check
                            |
                            v
                  precondition check
                            |
                            v
                         execute
                            |
                            v
                  independent verify
                            |
                 +----------+----------+
                 |                     |
                 v                     v
             RESOLVED              FAILED /
                                   ESCALATED
```

## 2.2 Verified hardening already present

- Multi-tenant endpoint ownership checks.
- RBAC.
- Credential-backed login support.
- SSE authentication and tenant matching.
- HMAC-based webhook authentication.
- Replay protection.
- Payload size/depth/string validation.
- Per-source-IP webhook rate limiting.
- 140 passing tests at the current baseline.
- CI.
- Real Temporal approval signal handling.
- Cancellation signal.
- Approval timeout and escalation.
- Plan hashing.
- LocalStack-backed execution verification.

Do not regress these features.

---

# 3. Architectural decisions that now become non-negotiable

## 3.1 Capability Gateway is the only production mutation path

This is the most important decision in the next phase.

### Rule

In production mode:

> **No operational mutation may execute outside the Capability Gateway.**

This means:

- no direct free-text action execution;
- no direct arbitrary tool-name execution;
- no unrestricted shell;
- no unrestricted SQL mutation;
- no direct cloud SDK write call from an agent;
- no bypass from `/execute`;
- no bypass from fallback logic;
- no bypass from admin/debug endpoints.

### Required behavior for unsupported actions

If an agent proposes an action that has no registered capability, return one of:

```text
UNSUPPORTED_CAPABILITY
```

or:

```text
MANUAL_ACTION_REQUIRED
```

Do not fall back to a weaker execution mechanism.

### Why

Only registered capabilities have the full safety path:

```text
intent
-> compile
-> policy
-> precondition
-> approval
-> execution-time recheck
-> execute
-> independent verification
```

That safety property must become universal.

## 3.2 Never resolve an incident on self-reported success

An action returning:

```text
{"status": "SUCCESS"}
```

must not be sufficient to resolve an incident.

Resolution must be based on independent verification.

Example:

```text
Action:
Retry Glue job

Execution result:
Started successfully

Verification:
- latest run status == SUCCEEDED
- output partition exists
- expected record-count bounds passed
- dependent workflow is no longer blocked
- no new critical alert appeared

Only then:
RESOLVED
```

## 3.3 Deterministic facts stay deterministic

Do not delegate these to the LLM:

- incident status;
- tenant identity;
- role authorization;
- impact counts;
- SLA arithmetic;
- plan hash;
- policy outcome;
- action status;
- verification result;
- capability availability;
- audit timestamps;
- current environment;
- whether an approval exists.

The model may explain these facts but must not invent them.

## 3.4 AI conclusions remain evidence-grounded

Every material AI claim should point to stored evidence.

Root-cause hypotheses must include:

- hypothesis ID;
- statement;
- confidence;
- supporting evidence IDs;
- contradicting evidence IDs;
- unknowns;
- recommended next evidence if confidence is insufficient.

---

# 4. Priority 1 — prove durability now

The workflow logic has improved significantly, but Temporal still runs as a dev-mode server.

Before changing architecture, run the durability test against the current system.

## 4.1 Durability test

### Scenario

1. Create or triage an incident.
2. Allow it to reach `AWAITING_APPROVAL`.
3. Record:
   - incident ID;
   - Temporal workflow ID;
   - plan ID;
   - plan hash.
4. Kill the FastAPI process/container.
5. Kill the Temporal worker.
6. Restart FastAPI.
7. Restart the worker.
8. Submit approval through the normal API.
9. Verify the workflow resumes.
10. Verify execution happens exactly once.
11. Verify action-execution records are not duplicated.
12. Verify independent verification occurs.
13. Verify final incident state.
14. Inspect the audit trail.

### Required assertions

```text
incident remained intact
plan remained intact
approval signal was received once
capability execution occurred once
verification occurred once
no duplicate mutation occurred
audit timeline remained coherent
```

### If this test fails

Do not add more capabilities until the durability defect is understood.

### Deliverable

Create:

```text
docs/testing/temporal_durability_test.md
```

Document:

- steps;
- environment;
- outcome;
- exact failure if any;
- relevant logs/trace IDs;
- remediation.

---

# 5. Priority 2 — move Temporal off dev mode

After current durability behavior is understood, replace the dev server for staging.

## 5.1 Deployment choices

Choose one:

### Option A — Temporal Cloud

Preferred when managed SaaS is acceptable.

### Option B — self-hosted production Temporal

Must include:

- persistent Temporal database;
- TLS;
- authenticated connections;
- namespace isolation;
- worker identity;
- production task queues;
- monitoring;
- retention policy;
- backup strategy;
- worker version/deployment compatibility.

## 5.2 Required staging tests

Repeat:

```text
AWAITING_APPROVAL
-> kill API
-> kill worker
-> restart
-> approve
-> execute exactly once
-> verify
```

Also test:

- approval timeout;
- cancellation;
- rejection;
- worker restart during execution;
- activity retry;
- duplicate approval attempt.

## 5.3 Acceptance criteria

Do not declare Temporal production-ready until:

- approval waits survive restarts;
- workflow histories are persistent;
- no duplicate writes occur;
- cancellation is durable;
- signals behave correctly;
- metrics are exported;
- connections are TLS/authenticated;
- namespace strategy is documented.

---

# 6. Priority 3 — remove the free-text execution safety gap

Current capability coverage remains narrow.

## 6.1 Production behavior

Change execution logic so that:

```text
mapped action
-> Capability Gateway

unmapped action
-> MANUAL_ACTION_REQUIRED
```

Do not allow:

```text
unmapped action
-> old free-text executor
```

## 6.2 Transitional compatibility

If the old path must remain for local development:

- hide it behind an explicit feature flag;
- default it OFF;
- prohibit it in production;
- show a visible warning in development;
- add tests proving production cannot use it.

Example:

```text
ALLOW_UNGOVERNED_ACTIONS=false
```

Production startup should fail if this is enabled.

---

# 7. Priority 4 — expand the Capability Gateway safely

Add only a few capabilities at a time.

## 7.1 Capability contract

Every new action capability must define:

```text
capability_id
version
description
resource_type
risk_level
autonomy_level
input_schema
permission_requirements
precondition_check
dry_run
execute
verify
rollback_or_compensate
idempotency_strategy
timeout
audit_class
```

## 7.2 Recommended next capabilities

### Capability A — Glue job rerun

```text
aws.glue.start_job_run
```

Requirements:

- verify job exists;
- confirm target environment;
- validate parameters;
- check whether an active run already exists;
- require approval at appropriate risk level;
- invoke the job;
- verify resulting run reaches expected state;
- verify output/data condition where possible.

### Capability B — Step Functions redrive/retry

```text
aws.stepfunctions.redrive_execution
```

Requirements:

- verify execution is eligible;
- validate redrive semantics;
- require approval;
- execute;
- verify new/redriven execution;
- inspect downstream state.

### Capability C — SQS DLQ redrive

```text
aws.sqs.redrive_dlq
```

Requirements:

- inspect queue depth;
- provide dry-run summary;
- calculate bounded message count;
- require approval;
- execute bounded redrive;
- verify source/destination behavior.

## 7.3 Tests required for every capability

- success;
- precondition failure;
- authorization failure;
- policy denial;
- execution failure;
- verification failure;
- duplicate request;
- timeout;
- rollback/compensation if applicable.

---

# 8. Priority 5 — fix business-impact quality

Current impact data is structurally real but not sufficiently differentiated. The current baseline shows constant/under-populated values such as:

```text
impact_score = 0.5
expected_breach_at = NULL
```

Fix this before investing further in business-risk visualization.

## 8.1 Separate technical impact from business severity

### Technical impact

Deterministic:

- downstream jobs;
- datasets;
- pipelines;
- services;
- resource count;
- blocked edges.

### Business impact

Derived from metadata:

- environment;
- data-product criticality;
- business tier;
- SLA;
- freshness requirement;
- expected breach time;
- downstream consumers;
- executive/customer-facing classification;
- revenue/operational impact band where available.

## 8.2 Suggested scoring model

Example:

```text
impact_score =
    environment_weight
  + criticality_weight
  + blast_radius_weight
  + sla_urgency_weight
  + consumer_weight
```

Normalize into:

```text
0.00 - 1.00
```

Do not let the model generate the numeric score.

The model may explain the score.

## 8.3 SLA calculation

Persist:

```text
expected_breach_at
minutes_to_breach
sla_status
```

Status example:

```text
HEALTHY
AT_RISK
BREACHED
UNKNOWN
```

## 8.4 Required UI output

Example:

```text
Business Risk: HIGH
Impact Score: 0.82
SLA breach expected in: 34 minutes
Affected data products: 3
Critical consumers: 2
```

---

# 9. Priority 6 — operationalize observability

OpenTelemetry is wired but lacks a real operational backend.

## 9.1 Add a trace backend

Use one of:

- Grafana Tempo;
- Jaeger;
- another OpenTelemetry-compatible backend.

## 9.2 Add a metrics backend

Use Prometheus/Grafana or equivalent.

## 9.3 One incident = one correlated trace

Correlation chain:

```text
request_id
incident_id
temporal_workflow_id
langgraph_run_id
agent_run_id
tool_call_id
capability_execution_id
verification_id
```

## 9.4 Required spans

### API

```text
ingest_webhook
triage_incident
approve_plan
cancel_incident
execute_plan
```

### Workflow

```text
incident_workflow
triage_activity
approval_wait
execute_activity
verification_activity
```

### Agent

```text
rca_agent
dependency_agent
runbook_agent
grounding_critic
```

### Capability

```text
compile
policy_check
precondition
dry_run
execute
verify
rollback
```

## 9.5 Initial dashboards

### Operations dashboard

- active incidents;
- workflow backlog;
- failed workflows;
- worker health;
- API errors.

### AI dashboard

- LLM latency;
- LLM errors;
- structured-output failures;
- tool calls per incident;
- investigation duration.

### Safety dashboard

- policy denials;
- approval time;
- verification failures;
- rollback count;
- unsupported capability count.

### Webhook security dashboard

- rejected payloads;
- replay attempts;
- invalid signatures;
- rate-limit hits.

---

# 10. Priority 7 — define product SLOs

Start with a small set.

## 10.1 Suggested SLOs

### Availability

```text
API availability >= 99.9%
```

### Webhook acceptance

For valid authenticated payloads:

```text
p95 ingest acknowledgement < 500 ms
```

### Investigation

Define a target for:

```text
p95 time to first useful hypothesis
```

after collecting baseline telemetry.

### Recovery plan

Define:

```text
p95 time to PLAN_READY
```

from observed baseline.

### Safety

```text
false RESOLVED rate = 0
```

This is the most important SLO.

### Workflow

Track:

```text
stuck workflow rate
```

### Verification

Track verification failure rate, but do not weaken verification merely to improve the metric.

---

# 11. Priority 8 — turn tests into a product evaluation suite

The current automated test baseline is strong. The next step is product-level evaluation.

## 11.1 Build 15–20 labelled incident scenarios

Required scenarios:

1. schema regression;
2. partial write;
3. missing source file;
4. late source file;
5. OOM crash;
6. credential failure;
7. API rate limit;
8. upstream service outage;
9. downstream constraint failure;
10. duplicate data;
11. disabled schedule;
12. bad deployment;
13. multiple simultaneous unrelated incidents;
14. duplicate noisy alerts;
15. false-positive alert;
16. unsafe rerun scenario;
17. stale data scenario;
18. Step Functions downstream failure;
19. DLQ accumulation;
20. transient infrastructure failure.

## 11.2 Scenario ground truth

Each scenario must define:

```text
scenario_id
root_cause
expected_primary_resource
expected_incident_cluster
expected_impacted_resources
expected_business_impact
expected_runbook
allowed_actions
unsafe_actions
verification_conditions
```

## 11.3 Metrics

Calculate:

### Correlation

- precision;
- recall.

### RCA

- top-1 accuracy;
- top-3 accuracy.

### Evidence

- citation coverage;
- unsupported-claim rate.

### Impact

- blast-radius recall;
- false-impact rate.

### Runbooks

- match accuracy.

### Safety

- unsafe-action prevention rate.

### Recovery

- successful verified recovery rate;
- rollback rate;
- false-resolution rate.

### Efficiency

- investigation time;
- model calls;
- tool calls;
- token usage;
- cost per incident.

## 11.4 Hard rule

The system must prefer:

```text
ESCALATE
```

over:

```text
FALSELY RESOLVED
```

---

# 12. Priority 9 — investigate Temporal test flakiness

The workflow test module is known to be nondeterministically flaky in the sandboxed test-server environment.

## 12.1 Required action

Run the workflow test suite repeatedly in actual CI.

Suggested:

```text
20 consecutive CI runs
```

Record:

- failure count;
- failure signature;
- runner;
- timing;
- Temporal SDK version;
- test-server version.

## 12.2 Decision

### If CI is stable

Document the local sandbox limitation.

Do not spend excessive engineering time on it.

### If CI is flaky

Fix the test harness before relying on it as a release gate.

Do not disable workflow testing.

---

# 13. Priority 10 — remove dead code

Now that the runtime path is established, remove confusing legacy paths.

## 13.1 Candidates

Verify and delete if truly unreachable:

```text
src/ui/
```

Legacy Streamlit UI.

Also evaluate:

```text
/api/v2/overview
```

if no live frontend path consumes it.

Evaluate:

- old SQLite store;
- obsolete MCP server;
- legacy read tools;
- legacy execution registry;
- unused Commander fallback code.

## 13.2 Removal policy

Delete only after:

- import search;
- route search;
- test search;
- runtime verification;
- replacement test coverage.

## 13.3 Documentation

Create:

```text
docs/architecture/CANONICAL_RUNTIME_PATH.md
```

It should explain exactly:

```text
event
-> incident
-> workflow
-> investigation
-> approval
-> capability
-> verification
```

This is especially important because AI coding agents may infer architecture from dead files.

---

# 14. Priority 11 — build the first real external integration

Do not immediately support every platform.

Choose one complete operational ecosystem.

## 14.1 Recommended first integration

AWS data pipelines:

- CloudWatch;
- Glue;
- S3;
- Step Functions.

## 14.2 Read capabilities

### CloudWatch

- alarms;
- logs;
- error signatures;
- metrics.

### Glue

- job configuration;
- job runs;
- error messages;
- worker type;
- arguments;
- execution time.

### S3

- object existence;
- last modified;
- size;
- expected partition;
- marker/control files where relevant.

### Step Functions

- execution state;
- failed state;
- execution history;
- downstream relationship.

## 14.3 Write capabilities

Start with only:

- Glue rerun;
- Step Functions redrive/retry.

Later:

- DLQ redrive;
- schedule pause/resume.

## 14.4 Least privilege

Use separate identities/policies for:

### Diagnostics

Read-only.

### Actions

Narrow writes.

Agents do not receive credentials directly.

The Capability Gateway owns credential use.

---

# 15. Priority 12 — runbook governance

Before action coverage becomes broad, formalize runbooks.

## 15.1 Runbook record

```text
runbook_id
version
title
owner
service
failure_type
environment
status
approved_by
approved_at
valid_from
expires_at
required_evidence
allowed_capabilities
preconditions
steps
verification
rollback
```

## 15.2 Lifecycle

```text
DRAFT
REVIEW
APPROVED
ACTIVE
DEPRECATED
RETIRED
```

## 15.3 Agent constraints

The model may:

- retrieve;
- match;
- explain;
- parameterize.

The model may not:

- approve a runbook;
- alter the source runbook;
- ignore expiration;
- bypass capability restrictions.

---

# 16. Priority 13 — administration

Once the control plane is safe, improve administration.

## 16.1 Capability administration

Show:

```text
Capability
Version
Risk
Autonomy
Enabled
Environment
Approval requirement
Dry-run requirement
Last execution
Success rate
```

## 16.2 Integration administration

Show:

```text
Integration
Tenant
Workspace
Environment
Status
Last successful connection
Last failure
Permissions
Credential expiry
```

Actions:

- test;
- disable;
- rotate credentials;
- inspect errors.

## 16.3 Model administration

Allow tenant/workspace policy for:

- RCA model;
- critic model;
- fallback model;
- timeout;
- token budget;
- provider;
- region/data residency.

## 16.4 Runbook administration

Support:

- owner;
- review;
- approve;
- expire;
- retire.

---

# 17. Priority 14 — auditability

The application must answer:

> Why did NemoGuard do this?

for every material action.

## 17.1 Required audit reconstruction

For an incident, reconstruct:

```text
alert received
correlation decision
incident created
investigation started
evidence retrieved
hypothesis created
critic outcome
plan created
plan hash
approval requested
approval granted/rejected
capability selected
policy evaluated
precondition result
execution result
verification result
final incident state
```

## 17.2 AI provenance

Record:

- model provider;
- model;
- prompt version;
- tool schema version;
- agent version;
- evidence references;
- structured result;
- latency;
- token usage.

Do not store hidden chain-of-thought.

---

# 18. Priority 15 — supportability

NemoGuard itself must be operable.

## 18.1 Support dashboard

Show:

- API health;
- DB health;
- Temporal health;
- workers;
- task queue backlog;
- model provider;
- connector health;
- workflow failures;
- stuck approvals;
- verification failures.

## 18.2 Support bundle

Generate a redacted support bundle containing:

```text
release version
migration version
service versions
workflow ID
incident ID
trace ID
connector statuses
recent application errors
```

Never include secrets.

---

# 19. What not to do now

The coding agent should **not** prioritize:

- another major frontend redesign;
- adding ten more agents;
- model fine-tuning;
- multi-cloud support;
- mobile apps;
- generic shell execution;
- arbitrary SQL actions;
- Kubernetes migration;
- replacing PostgreSQL;
- replacing FastAPI;
- replacing LangGraph;
- replacing Temporal;
- microservice-per-agent architecture.

The stack is already capable.

The next phase is about trust.

---

# 20. Recommended next five work packages

## WP-008 — Durability & Production Temporal Readiness

### Objective

Prove restart durability and prepare a persistent Temporal staging deployment.

### Tasks

1. Run durability test on current stack.
2. Record exact behavior.
3. Fix duplicate-execution defects if any.
4. Add idempotency assertions.
5. Select Temporal Cloud or self-hosted.
6. Deploy staging-grade Temporal.
7. Enable TLS/auth.
8. Define namespace strategy.
9. Export metrics.
10. Repeat restart test.
11. Test cancel/reject/timeout across restart.

### Acceptance criteria

- workflow survives process restart;
- approval resumes correctly;
- execution is logically exactly once;
- action idempotency is verified;
- cancellation survives restart;
- audit remains coherent.

---

## WP-009 — Governed Execution Only

### Objective

Eliminate weaker action paths in production.

### Tasks

1. Inventory every path capable of mutation.
2. Route all supported mutations through Capability Gateway.
3. Disable free-text fallback in production.
4. Return `MANUAL_ACTION_REQUIRED` for unsupported actions.
5. Add a production configuration guard.
6. Add tests proving bypass is impossible.
7. Audit bypass attempts.

### Acceptance criteria

There is no production runtime path from LLM output directly to mutation.

---

## WP-010 — Business Impact Engine

### Objective

Replace placeholder impact values with deterministic differentiated business risk.

### Tasks

1. Define required metadata.
2. Implement scoring.
3. Compute SLA breach time.
4. Persist business criticality.
5. Add high/medium/low-impact tests.
6. Update UI.
7. Remove constant impact placeholders.

### Acceptance criteria

Different incidents produce meaningfully different impact results for explainable reasons.

---

## WP-011 — Observability & SLOs

### Objective

Make NemoGuard itself operable.

### Tasks

1. Deploy trace backend.
2. Deploy metrics backend.
3. Propagate trace IDs.
4. Add spans.
5. Build dashboards.
6. Define SLOs.
7. Add alerts.
8. Add incident-level trace links in UI/admin.

### Acceptance criteria

An engineer can trace a production incident from webhook to verification using one incident ID.

---

## WP-012 — Capability Expansion & AWS Pilot

### Objective

Add governed AWS remediation and prove it against a real non-production environment.

### Tasks

1. Add Glue rerun capability.
2. Add Step Functions redrive capability.
3. Optionally add DLQ redrive.
4. Add least-privilege IAM.
5. Add preconditions.
6. Add dry run.
7. Add independent verification.
8. Add failure tests.
9. Run against non-production AWS.
10. Capture audit evidence.

### Acceptance criteria

At least one real non-production failure is diagnosed, approved, remediated, verified, and fully audited through NemoGuard.

---

# 21. Thirty-day execution order

## Week 1

### Primary goals

- durability verification;
- disable unsafe fallback;
- clean dead code;
- investigate Temporal test behavior in CI.

### Deliverables

- durability report;
- production-mode execution guard;
- canonical runtime documentation;
- dead-code cleanup PR.

## Week 2

### Primary goals

- business impact engine;
- SLA calculations;
- evaluation dataset expansion.

### Deliverables

- differentiated impact;
- time-to-breach;
- labelled scenario suite;
- baseline evaluation report.

## Week 3

### Primary goals

- observability backend;
- trace correlation;
- SLOs.

### Deliverables

- traces;
- metrics;
- dashboards;
- alert rules.

## Week 4

### Primary goals

- new capabilities;
- AWS pilot integration.

### Deliverables

- Glue rerun;
- Step Functions redrive;
- independent verification;
- non-production pilot.

---

# 22. Product quality gates

Do not move to a broader pilot until these pass.

## Gate A — Safety

- all writes through Capability Gateway;
- no free-text production mutation;
- approval policy enforced;
- plan hash enforced;
- execution-time policy recheck;
- independent verification.

## Gate B — Durability

- workflow survives restarts;
- approval survives restart;
- execution does not duplicate;
- idempotency proven.

## Gate C — Security

- tenant isolation;
- RBAC;
- webhook authentication;
- replay protection;
- rate limits;
- auth on SSE.

## Gate D — Audit

- complete timeline;
- actor attribution;
- model/tool provenance;
- policy version;
- verification record.

## Gate E — Evaluation

- labelled scenarios;
- correlation metrics;
- RCA metrics;
- unsafe-action prevention;
- false-resolution measurement.

---

# 23. Most important metric

The most important safety metric is:

```text
FALSE RESOLUTION RATE
```

Target:

```text
0
```

A false positive RCA can be corrected.

A false resolution can cause operators to believe production is healthy when it is not.

Therefore:

```text
verification uncertain
-> ESCALATE
```

not:

```text
verification uncertain
-> RESOLVED
```

---

# 24. Product success metrics

## Reliability

- incidents correctly correlated;
- verified recovery rate;
- rollback rate;
- stuck workflow rate.

## AI quality

- RCA top-1;
- RCA top-3;
- unsupported-claim rate;
- critic disagreement.

## Efficiency

- time to first hypothesis;
- time to recovery plan;
- human approval time;
- MTTR.

## Safety

- policy blocks;
- unsupported action count;
- verification failures;
- false resolutions.

## Cost

- model calls per incident;
- token use per incident;
- cost per incident.

---

# 25. Technical principle for future connectors

Do not let connectors own mutation policy.

Correct:

```text
Connector
= transport / system adapter

Capability Gateway
= mutation authority
```

Example:

```text
AWSConnector
  read Glue run
  read logs
  read Step Function

GlueRerunCapability
  policy
  precondition
  execute
  verify
```

This keeps safety consistent across integrations.

---

# 26. Technical principle for future AI features

A new AI feature must answer:

1. What deterministic data does it consume?
2. What evidence will support its output?
3. Can the output cause a mutation?
4. If yes, what capability controls it?
5. How will it be independently verified?
6. How will it be audited?
7. How will it be evaluated?

If those questions cannot be answered, do not ship the feature.

---

# 27. Coding-agent operating instructions

Before each work package:

1. Inspect current code.
2. Identify the active runtime path.
3. Identify existing tests.
4. Avoid modifying unrelated components.
5. Add tests first or alongside implementation.
6. Preserve backward compatibility where possible.
7. Document migrations.
8. Run the full test suite.
9. Run the frontend production build.
10. Run the relevant end-to-end flow.

After each work package, report:

```text
WORK PACKAGE:
STATUS:

FILES CHANGED:

MIGRATIONS:

CONFIG CHANGES:

TESTS ADDED:

TEST RESULTS:

E2E RESULTS:

SECURITY IMPACT:

OBSERVABILITY IMPACT:

BACKWARD COMPATIBILITY:

KNOWN LIMITATIONS:

ROLLBACK PROCEDURE:

NEXT RECOMMENDED ACTION:
```

Do not accept "implemented" without test evidence.

---

# 28. First action for the coding agent

Start with:

> **WP-008 — Durability & Production Temporal Readiness**

But before deploying a new Temporal architecture, first run the current durability test.

This provides evidence about what actually breaks today.

Do not prematurely refactor.

---

# 29. Final product direction

NemoGuard should evolve toward:

> **A governed autonomous operations platform for data reliability.**

It should not compete primarily on having the most agents.

It should compete on:

- trustworthy diagnosis;
- explainable evidence;
- deterministic safety;
- controlled action;
- independent verification;
- complete auditability;
- durable execution.

The product should earn the right to automate progressively.

Recommended autonomy ladder:

```text
Level 0
Read-only diagnosis

Level 1
Recommend actions

Level 2
Human-approved execution

Level 3
Automatic low-risk action

Level 4
Automatic bounded recovery with verification

Level 5
Broader autonomous remediation
```

Do not jump levels.

Automation should increase per capability based on observed safety and reliability.

---

# 30. Non-negotiable end state

The following flow must remain true as the product grows:

```text
Alert arrives
    |
    v
Deterministic normalization/correlation
    |
    v
Durable incident workflow
    |
    v
Evidence-grounded AI investigation
    |
    v
Recovery intent
    |
    v
Deterministic capability compilation
    |
    v
Authorization + policy + preconditions
    |
    v
Human approval if required
    |
    v
Execution
    |
    v
Independent verification
    |
    +--> verified -> RESOLVED
    |
    +--> uncertain/failure -> ESCALATE / ROLLBACK
```

If a future implementation bypasses this principle for convenience, treat it as an architectural regression.

---

# END OF EXECUTION PLAN
