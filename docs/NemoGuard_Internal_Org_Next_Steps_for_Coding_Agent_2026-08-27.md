# NemoGuard — Internal Organization Build Roadmap: Next Steps for the Coding Agent

**Date:** 2026-08-27  
**Primary objective:** Build NemoGuard first as an internal, trusted data-reliability and recovery platform for the organization — not as a SaaS product.

## 0. Strategic direction

Do not optimize NemoGuard for SaaS packaging, billing, public multi-tenancy, marketplace distribution, or generalized customer onboarding at this stage.

The near-term mission is:

> Make NemoGuard exceptionally good at understanding and safely recovering incidents in our own organization's data platforms, using our own topology, runbooks, incident history, operational practices, business SLAs, and recovery outcomes.

The product intelligence should become:

```text
Foundation Model
+ Live Tools
+ Organizational Knowledge
+ Incident Memory
+ Historical Incident Replay
+ Deterministic Policy
+ Governed Capability Execution
+ Independent Verification
+ Continuous Evaluation
```

Do not assume a 550B model is good enough because of parameter count. Trust must be created through measurable evaluation on the exact failure patterns our organization experiences.

---

# 1. Preserve the control model

```text
AI:
- investigates
- reasons
- ranks hypotheses
- requests evidence
- recommends recovery

Deterministic platform:
- authenticates
- authorizes
- scopes environment
- validates incident state
- evaluates risk
- validates approval
- validates plan hash
- enforces capability policy
- checks preconditions
- guarantees idempotency where possible

Capability layer:
- executes approved actions

Verification layer:
- independently validates infrastructure, pipeline, and data health

Only then:
INCIDENT = RESOLVED
```

Never move execution authority into the LLM.

---

# 2. New priority order

## P0 — Organizational intelligence foundation
1. Historical Incident Replay
2. Incident Memory
3. Model Evaluation Service
4. Upgrade the current scenario suite into a formal scored benchmark
5. Fix terminal-incident correlation semantics

## P1 — Organizational context
6. Internal operations catalog
7. Data lineage and business dependency model
8. Runbook knowledge layer
9. Change/deployment history integration
10. Ownership and SLA context

## P2 — Real-world validation
11. Shadow-mode pilot
12. Human-vs-NemoGuard comparison capture
13. Confidence calibration
14. Model comparison harness
15. Pilot-driven tool/capability expansion

## P3 — Enterprise hardening
16. Production-like Temporal
17. Operationalize OpenTelemetry
18. Audit/evidence package
19. Runbook governance
20. Internal administration

## P4 — Optional later work
21. Fine-tuning or distillation
22. More autonomous low-risk actions
23. Broader platform integrations
24. PagerDuty/ServiceNow/Teams integration
25. SaaS-oriented capabilities only if ever needed

---

# 3. WP-ORG-001 — Historical Incident Replay

## Goal

Build a subsystem that replays historical organizational incidents as if they were happening again, without exposing the final human root cause to the AI.

This is the single most important next capability for proving whether the current Nemotron reasoning stack is actually good enough for the organization's real operational workload.

## Required behavior

For a past incident, collect only the information that was available during the incident:

```text
alerts
logs
job states
pipeline state
deployment/change history
schema information
data quality information
topology
runbooks available at that time
ticket metadata
```

Do not expose until scoring:

```text
final RCA
final postmortem
final successful action
human resolution notes
```

## Suggested data model

```text
historical_incident
historical_incident_snapshot
historical_incident_ground_truth
historical_incident_replay
historical_incident_replay_result
```

Suggested fields:

### historical_incident
```text
id
external_incident_id
source_system
opened_at
resolved_at
service
pipeline
environment
severity
```

### historical_incident_snapshot
```text
incident_id
snapshot_type
snapshot_timestamp
source_reference
payload_json
```

### historical_incident_ground_truth
```text
incident_id
root_cause
cause_type
actual_recovery
actual_impacted_assets
actual_business_impact
actual_resolution_time
postmortem_reference
```

### historical_incident_replay
```text
id
historical_incident_id
model_provider
model_name
prompt_version
started_at
completed_at
status
```

### replay_result
```text
top_hypothesis
top_hypothesis_score
top_3_hypotheses
selected_runbook
recommended_plan
tool_calls
evidence_ids
elapsed_seconds
```

## Replay API

```text
POST /api/v2/replay/incidents/{historical_incident_id}
GET  /api/v2/replay/{replay_id}
GET  /api/v2/replay/{replay_id}/result
```

## Replay execution flow

```text
Historical incident
    ↓
Load point-in-time evidence
    ↓
Create isolated replay context
    ↓
Run same investigation graph used for live incidents
    ↓
Do NOT expose write capabilities
    ↓
Persist hypotheses/evidence/plan
    ↓
Compare against hidden ground truth
    ↓
Score
```

## UI

Add to Scenario Cockpit:

```text
Lab Scenarios
Historical Replay
Live Shadow
```

Historical Replay should show:

```text
Incident
Date
System
Known severity
Replay status
Top-1 result
Top-3 result
Agreement with human RCA
Time to RCA
```

## Acceptance criteria

- historical incidents can be replayed
- ground truth remains hidden during investigation
- no write capabilities can execute
- replay result is persisted
- score is calculated
- replay can be repeated with different models

---

# 4. WP-ORG-002 — Incident Memory

## Goal

Create a governed memory layer that allows future incidents to benefit from previous resolved incidents.

Do not rely on model training to remember organizational knowledge.

## Memory record

```text
incident_id
failure_signature
service
pipeline
environment
root_cause
cause_type
supporting_evidence
contradicting_evidence
successful_recovery
failed_recovery_attempts
runbook_used
capabilities_used
verification_result
data_integrity_result
human_feedback
mttr
tags
created_at
reviewed_by
memory_status
```

## Memory lifecycle

```text
DRAFT
REVIEWED
APPROVED
REJECTED
REDACTED
EXPIRED
```

Do not automatically trust every AI-generated lesson.

## Similarity retrieval

```text
new incident
    ↓
derive structured failure signature
    ↓
search incident memory
    ↓
retrieve top similar incidents
    ↓
present as historical evidence
```

Example:

```text
94% similar to INC-3291

Previous cause:
Schema contract violation

Previous recovery:
Update mapping and replay affected partition

Verification:
12.8M rows
0 duplicate keys
schema PASS
```

Users must be able to view, edit, approve, reject, redact, and delete memory as policy permits.

Historical recovery remains evidence; it must never bypass current preconditions, policy, approval, or verification.

## Acceptance criteria

- resolved incidents generate draft memory
- humans can review memory
- approved memory participates in future investigation
- memory retrieval is visible in the UI
- stale/rejected memory is excluded
- historical recovery cannot bypass safety controls

---

# 5. WP-ORG-003 — Model Evaluation Service

## Goal

Make model quality measurable.

The system must be able to answer:

> Is Nemotron Ultra actually better for our incidents than Nemotron Super or another approved model?

without guessing.

## Provider abstraction

Use one structured provider interface for:

```text
Nemotron Ultra
Nemotron Super
other organization-approved models
future local models
```

## Evaluation sources

```text
Scenario Catalog
Historical Incident Replay
Live Shadow Incidents
```

## Required metrics

### RCA
```text
Top-1 accuracy
Top-3 accuracy
cause-family accuracy
```

### Evidence
```text
evidence citation coverage
unsupported claim rate
contradictory evidence handling
```

### Tool behavior
```text
correct tool selection
unnecessary tool count
tool loop count
tool failure recovery
```

### Recovery
```text
correct runbook selection
safe action selection
unsafe action recommendation rate
verification completeness
```

### Performance
```text
latency
input tokens
output tokens
tool calls
estimated cost
```

## Scorecard

Example only:

```text
MODEL                  TOP1   TOP3   UNSUPPORTED   SAFE PLAN   P95 LATENCY

Nemotron Super         ...    ...       ...           ...          ...
Nemotron Ultra         ...    ...       ...           ...          ...
Model C                ...    ...       ...           ...          ...
```

Never hardcode result values.

## Release gate

Any model change must pass a repeatable evaluation command before deployment.

## Acceptance criteria

- same incident suite runs against multiple models
- results stored separately
- scorecard generated
- prompt/model versions tracked
- model changes cannot silently reach production

---

# 6. WP-ORG-004 — Upgrade the Scenario Catalog

Turn pass/fail validation into a scored benchmark.

Every scenario should define:

```text
expected_root_cause
expected_cause_family
expected_incident_count
expected_primary_resource
expected_impact
expected_runbook
allowed_actions
prohibited_actions
expected_verification
expected_terminal_state
```

Calculate:

```text
RCA Top-1
RCA Top-3
correlation correctness
alert compression
evidence coverage
blast radius recall
safe action rate
unsafe action block rate
verification accuracy
false resolution rate
```

False resolution definition:

```text
incident status = RESOLVED
AND
required verification checks are not actually satisfied
```

Target:

```text
0
```

Grow the catalog toward 50+ cases covering:

```text
terminal recurrence
verification failures
model timeout
invalid structured output
tool unavailable
conflicting evidence
no runbook
invalid HMAC
replay attack
cross-environment access
viewer execution attempt
stale plan hash
plan changed after approval
prompt injection in logs
```

---

# 7. WP-ORG-005 — Fix terminal-incident correlation

A new actionable alert must not attach directly to an old terminal incident.

Active candidates:

```text
DETECTED
CORRELATING
TRIAGING
INVESTIGATING
PLAN_READY
AWAITING_APPROVAL
EXECUTING
VERIFYING
NEEDS_REVIEW
```

Terminal:

```text
RESOLVED
FAILED
CANCELLED
CLOSED
```

Desired behavior:

```text
new alert
    ↓
search open incidents
    ↓
match?
   /    yes    no
  |      |
attach  create new incident
             ↓
      search historical similarity
             ↓
       create recurrence link
```

Acceptance criteria:

- terminal incidents excluded from candidate set
- active same-cause incident still correlates
- historical recurrence retained
- old incident never silently reopens
- regression scenarios added

---

# 8. WP-ORG-006 — Internal Operations Catalog

Create a deterministic model of the organization's operational universe.

Entities:

```text
business capability
business data product
dataset
table
file feed
pipeline
workflow
job
service
application
cloud resource
owner/team
environment
SLA
runbook
```

Relationships:

```text
business capability
    ↓ depends on
data product
    ↓ produced by
pipeline
    ↓ contains
job
    ↓ reads/writes
dataset
    ↓ hosted on
infrastructure
```

Possible sources:

```text
existing CMDB
pipeline metadata
Databricks jobs
Glue jobs
Step Functions
PowerCenter metadata
S3 conventions
database metadata
manual onboarding
```

Acceptance criteria:

- incident can resolve job -> dataset -> product -> owner
- impact calculations use catalog data
- the model does not invent relationships
- provenance is visible

---

# 9. WP-ORG-007 — Data Lineage & Business Impact

Build the lineage graph:

```text
Source
  ↓
Ingestion
  ↓
Bronze
  ↓
Silver
  ↓
Gold
  ↓
Data Product
  ↓
Dashboard/API/ML/Business Process
```

Impact engine should deterministically compute:

```text
affected downstream jobs
affected datasets
affected products
affected business capabilities
owners
SLA exposure
```

AI may explain these results, but should not invent counts.

---

# 10. WP-ORG-008 — Data Integrity Engine

This should become a major differentiator.

Deterministic integrity checks:

```text
schema contract
expected partitions
expected files
row counts
duplicate keys
null thresholds
freshness
volume anomaly
referential integrity
watermarks
CDC offsets
checkpoint consistency
partial writes
```

Verification should consider:

```text
Infrastructure Health
+
Pipeline Health
+
Data Health
+
Downstream Health
+
Business Data Health
```

Example:

```text
Infrastructure
✓ Lambda healthy
✓ Glue run succeeded

Pipeline
✓ workflow completed
✓ downstream jobs unblocked

Data
✓ schema valid
✓ partition exists
✓ row count correct
✓ duplicate count = 0
✓ freshness restored

Business
✓ data product current
✓ SLA restored
```

Only then mark RESOLVED when the policy requires those checks.

---

# 11. WP-ORG-009 — Recovery Safety Profiles

Every write capability must understand data side effects.

Example:

```text
Capability:
retry_job

Writes data: YES
Idempotent: UNKNOWN
Partial output possible: YES
Checkpoint support: YES

Required preconditions:
- detect partial output
- inspect checkpoint
- verify target partition

Required verification:
- row count
- duplicate check
- freshness
```

Another:

```text
Capability:
restart_stateless_lambda

Writes data: NO
Idempotent: YES
Risk: LOW
```

Acceptance criteria:

- each write capability declares data side effects
- required preconditions are enforced
- verification requirements are capability-specific
- plans cannot bypass safety profiles

---

# 12. WP-ORG-010 — Runbook Knowledge Layer

Use approved operational knowledge instead of relying on model memory.

Runbook schema:

```text
runbook_id
version
service
failure_family
environment
owner
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

Investigation behavior:

```text
RCA
  ↓
Runbook retrieval
  ↓
Approved active runbooks only
  ↓
adapt parameters
  ↓
policy
```

---

# 13. WP-ORG-011 — Change & Deployment Intelligence

Make recent changes a first-class RCA input.

Integrate where practical:

```text
Git commits
CI/CD deployments
Databricks bundle deployments
Glue configuration changes
Lambda deployments
Step Functions changes
PowerCenter deployments
schema migrations
AppFlow configuration changes
```

RCA should be able to explain:

```text
Failure began 6 minutes after deployment DEP-442.

Deployment changed:
loyalty_id -> member_id

3 previous runs succeeded before the change.
```

---

# 14. WP-ORG-012 — Shadow Mode Pilot

Validate NemoGuard on real organizational incidents before enabling production writes.

Allowed:

```text
ingest
correlate
investigate
retrieve memory
retrieve runbooks
calculate impact
recommend
```

Disabled:

```text
production mutation
```

For each incident capture:

```text
human_root_cause
nemoguard_top1
nemoguard_top3
human_action
nemoguard_recommendation
human_time_to_rca
nemoguard_time_to_rca
human_agreement
operator_feedback
```

Target:

```text
50-100 real incidents
```

---

# 15. WP-ORG-013 — Human Feedback Capture

At resolution, ask:

```text
Was the primary RCA correct?
Yes / Partially / No

Was the recovery recommendation useful?
Yes / Partially / No

What did NemoGuard miss?

What evidence was most useful?

Was any recommendation unsafe?

Should this incident become approved memory?
```

Preserve:

```text
AI decision
human correction
final outcome
```

Do not overwrite the original model output.

---

# 16. WP-ORG-014 — Confidence Calibration

Do not display raw LLM confidence as statistically meaningful.

Bucket predictions:

```text
90-100%
80-89%
70-79%
60-69%
```

Measure actual correctness per bucket.

Store:

```text
raw confidence
calibrated confidence
```

The UI should ultimately display calibrated confidence.

---

# 17. WP-ORG-015 — Production-like Temporal

Move from dev-mode Temporal to an internally supportable deployment.

Requirements:

```text
persistent Temporal database
TLS
authenticated connections
namespace
worker versioning
monitoring
backup strategy
```

Required durability test:

```text
incident reaches AWAITING_APPROVAL
kill API
kill worker
restart
approve
same workflow resumes
action runs once
verification runs once
```

---

# 18. WP-ORG-016 — Operational Observability

Operationalize OpenTelemetry using an internal stack such as:

```text
OpenTelemetry Collector
Tempo/Jaeger
Prometheus
Grafana
```

Track:

```text
incident processing latency
model latency
model failures
tool failures
workflow failures
approval timeout
capability failures
verification failures
reinvestigation frequency
```

---

# 19. WP-ORG-017 — Model Routing

Do not use Ultra 550B for everything.

Suggested routing:

### Deterministic / no LLM
```text
normalization
deduplication
topology traversal
impact counts
SLA arithmetic
policy
verification
```

### Smaller model
```text
classification
log summarization
entity extraction
title generation
```

### Nemotron Super
```text
common RCA
tool selection
runbook matching
impact explanation
```

### Nemotron Ultra
```text
complex RCA
conflicting evidence
multi-system failure
critic
replanning
```

Acceptance criteria:

- routing policy configurable
- evaluation proves no unacceptable quality regression
- model choice included in audit
- cost and latency measured

---

# 20. WP-ORG-018 — Fine-Tuning Decision Gate

Do not fine-tune merely because organizational data exists.

Consider fine-tuning only after replay/shadow evidence shows repeated reasoning failure patterns such as:

```text
same cause family repeatedly misclassified
same recovery family consistently ranked incorrectly
organization-specific terminology repeatedly misunderstood
tool selection repeatedly wrong despite correct context
```

Collect:

```text
input evidence
AI answer
human correction
correct RCA
correct plan
execution result
verification outcome
```

Before fine-tuning ask:

1. Can retrieval fix it?
2. Can better tools fix it?
3. Can prompt/schema changes fix it?
4. Can deterministic code fix it?
5. Is the failure genuinely model reasoning?

Only then consider fine-tuning or distillation.

---

# 21. WP-ORG-019 — Pilot-Driven Capability Expansion

Do not create generic AWS execution.

Rank proposed capabilities using:

```text
frequency
× operator time saved
× safety feasibility
× verification feasibility
```

Possible examples:

```text
Glue retry/stop
Step Functions redrive
AppFlow start
SQS redrive
Databricks rerun
partition verification
schema verification
data validation
```

---

# 22. WP-ORG-020 — PagerDuty / ITSM Integration Later

Do not rebuild mature on-call and communication systems unnecessarily.

Potential integrations:

```text
PagerDuty
ServiceNow
Teams
Slack
```

Example:

```text
PagerDuty incident
    ↓
NemoGuard investigates data incident
    ↓
posts RCA/impact
    ↓
human approves in NemoGuard
    ↓
NemoGuard executes and verifies
    ↓
PagerDuty updated
```

This should not block internal adoption.

---

# 23. Deprioritize SaaS-only work

For now, do not prioritize:

```text
billing
customer subscription management
public marketplace
cross-customer benchmarking
public signup
SaaS onboarding wizard
external tenant billing
commercial packaging
```

Keep necessary internal RBAC/workspace isolation.

---

# 24. Keep internal administration

Still build internal admin for:

```text
users
roles
workspaces
integrations
runbooks
capabilities
model configuration
policy
audit
```

---

# 25. Validation ladder

Progress through:

```text
30 current lab scenarios
        ↓
50 adversarial/negative scenarios
        ↓
100 historical incident replays
        ↓
50-100 live shadow incidents
        ↓
human-approved non-production recovery
        ↓
human-approved production recovery
        ↓
automatic low-risk recovery only if proven safe
```

---

# 26. Suggested engineering gates

These are engineering targets, not universal standards.

Before medium-risk automated execution:

```text
RCA Top-1                     > 80%
RCA Top-3                     > 95%
Evidence coverage             > 95%
Unsupported material claims   < 2%
Blast-radius accuracy         > 95%
Unsafe action blocking        100%
Unauthorized action blocking  100%
Verification correctness      ~100%
False resolution              0%
```

False resolution is the hardest gate.

---

# 27. Release targets

## NemoGuard Alpha 2 — Organizational Intelligence

Required:

```text
Historical Incident Replay
Incident Memory
Model Evaluation Service
50-scenario scored benchmark
terminal correlation fixed
impact engine validated
data integrity verification baseline
```

## NemoGuard Beta — Shadow Operations

Required:

```text
real internal alert integration
50+ shadow incidents
human comparison metrics
confidence calibration
production-like Temporal
observability
internal runbook knowledge
```

## NemoGuard Assisted Operations

Required:

```text
human-approved real recovery
governed capabilities
idempotency
independent data verification
rollback/compensation
complete audit
```

---

# 28. Likely implementation areas

Inspect the repository before renaming or creating files, but likely areas include:

```text
src/domain/
  replay/
  memory/
  evaluation/
  impact/
  lineage/

src/domain/agents/
  langgraph_investigator.py
  rca_agent.py
  runbook_agent.py

src/capabilities/
  registry.py
  policy.py
  execution_engine.py

src/api/
  replay endpoints
  memory endpoints
  evaluation endpoints

src/store/
  replay/memory/evaluation repositories

migrations/
  historical incidents
  incident memory
  replay results
  evaluation results
  recurrence relationships

frontend/src/
  Historical Replay
  Incident Memory
  Model Evaluation
  Adoption Readiness

scripts/
  evaluate_model.py
  import_historical_incidents.py
  run_historical_replay_suite.py
```

---

# 29. First work package — start now

## WP-ORG-001 — Historical Incident Replay

Deliver:

1. Historical incident domain model.
2. Point-in-time evidence snapshot model.
3. Hidden ground-truth model.
4. Read-only replay execution mode.
5. Replay API.
6. Replay result persistence.
7. Replay scoring.
8. UI list/detail view.
9. Unit tests.
10. Integration tests.
11. Documentation.

Important constraint:

> Replay must use the same investigation code path as live incidents wherever possible.

Do not create a separate simplified AI pipeline just for replay.

---

# 30. WP-ORG-001 acceptance test

Create one historical-style fixture.

Example:

```text
Incident:
schema regression

Visible evidence:
- CloudWatch error
- KeyError
- recent deployment
- prior successful runs
- current schema metadata

Hidden ground truth:
SCHEMA_REGRESSION
```

Expected:

```text
Replay completes
Top-1 = SCHEMA_REGRESSION
No write tools exposed
Result stored
Score calculated
```

---

# 31. Next work packages

After WP-ORG-001:

> WP-ORG-002 — Incident Memory

Then:

> WP-ORG-003 — Model Evaluation Service

Then:

> WP-ORG-004 — Scored Scenario Benchmark

Then:

> WP-ORG-005 — Terminal Correlation Fix

Continue in the priority order above.

---

# 32. Coding agent completion report format

After every work package return:

```text
WORK PACKAGE:
STATUS:

FILES CHANGED:

MIGRATIONS:

API CHANGES:

UI CHANGES:

TESTS ADDED:

TEST RESULTS:

SCENARIOS / REPLAYS ADDED:

METRICS:

SECURITY IMPACT:

DATA GOVERNANCE IMPACT:

BACKWARD COMPATIBILITY:

KNOWN LIMITATIONS:

ROLLBACK PROCEDURE:

NEXT RECOMMENDATION:
```

Do not report "done" without test evidence.

---

# 33. Final guidance

The next intelligence advantage should come from organizational context, not blindly increasing model size.

Improve NemoGuard through:

```text
more relevant evidence
better tools
better organizational topology
better data lineage
better runbooks
incident memory
human feedback
historical replay
evaluation
```

The goal is not:

> Train a model with billions of events.

The goal is:

> Build an operational intelligence system that can repeatedly prove it understands the incidents this organization actually experiences.

The correct progression is:

```text
Generic model
    +
Organization-specific context
    +
Historical incidents
    +
Human decisions
    +
Recovery outcomes
    +
Continuous evaluation
    =
Organization-specific operational intelligence
```

That is the path NemoGuard should follow next.
