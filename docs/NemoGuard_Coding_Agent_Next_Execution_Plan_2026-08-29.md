# NemoGuard — Coding Agent Next Execution Plan

**Date:** 2026-08-29  
**Baseline:** `enterprise-hardening`, clean working tree, latest migration `016_model_evaluation.sql`  
**Primary source:** `SESSION_STATUS_2026-08-29.md`

## Mission

The next phase is not primarily about adding more agents. The objective is to turn NemoGuard into a measurable, organization-aware, data-reliability platform that can be trusted first in shadow mode and later in human-approved real operations.

Preserve this control model:

```text
AI investigates and recommends
        ↓
Deterministic platform validates identity, state, plan, policy, and preconditions
        ↓
Human approval where required
        ↓
Typed capability executes
        ↓
Independent verification proves infrastructure + pipeline + data recovery
        ↓
Only then RESOLVED
```

Do not weaken this separation.

---

# 1. Do not re-implement completed work

The following are already implemented and live-validated:

- Historical Incident Replay
- Commander Live
  - Ask
  - Guide
  - Add Fact
  - conversation memory
  - chat-triggered reinvestigation
- Commander Pulse
- Teams Incident Communications Phase A
- Incident Memory lifecycle and similarity retrieval
- Model Evaluation Service
- model override through all major investigation agents
- historical incident recurrence linking
- False Resolution Rate audit
- 141/141 unit tests
- current 30-scenario real-failure validation catalog
- governed Capability Gateway
- real approval and independent verification

Do not fork or replace these unless a specific regression is proven.

---

# 2. Priority order

Execute in this order:

```text
WP-029-001  Finish Scored Validation Benchmark
WP-029-002  Expand Scenario Catalog to 50+
WP-029-003  Internal Operations Catalog
WP-029-004  Data Lineage & Business Dependency Graph
WP-029-005  Data Integrity Engine
WP-029-006  Recovery Safety Profiles
WP-029-007  Commander Intervention Analytics
WP-029-008  Human-vs-NemoGuard Comparison Capture
WP-029-009  Confidence Calibration
WP-029-010  Shadow Mode Pilot Foundation
WP-029-011  Production-like Temporal
WP-029-012  Operationalize OpenTelemetry
WP-029-013  Audit/Evidence Package Verification
WP-029-014  Runbook Knowledge & Governance
WP-029-015  Teams Phase B
WP-029-016  Pilot-driven Capability Expansion
```

Do not jump to remediation expansion before the evaluation, context, and integrity layers are stable.

---

# 3. WP-029-001 — Finish Scored Validation Benchmark

## Goal

Complete the evaluation framework. False Resolution Rate exists; the rest must become real metrics.

## Required metrics

### RCA
- Top-1 accuracy
- Top-3 accuracy
- cause-family accuracy

### Correlation
- correlation correctness
- precision
- recall
- alert compression ratio

### Evidence
- evidence coverage
- unsupported material claim rate
- contradictory evidence handling

### Impact
- blast-radius recall
- blast-radius precision

### Recovery
- runbook selection accuracy
- safe action selection rate
- unsafe action block rate

### Verification
- verification accuracy
- false resolution rate

## Ground-truth schema

Every scenario must define machine-readable expected outcomes:

```json
{
  "scenario_id": "INGEST-SCHEMA-DRIFT",
  "ground_truth": {
    "cause_family": "SCHEMA_REGRESSION",
    "expected_incident_count": 1,
    "expected_primary_resource": "nemoguard-ingest-job",
    "expected_capabilities": ["compute.rerun_ingest_job"],
    "prohibited_capabilities": [],
    "expected_terminal_state": "RESOLVED",
    "verification_requirements": [
      "job_success",
      "expected_output_present"
    ]
  }
}
```

## Evaluation result

Store per-run:

```text
scenario_id
evaluation_run_id
model_name
prompt_version
top1_root_cause
top1_correct
top3_correct
evidence_coverage
unsupported_claim_count
expected_incident_count
actual_incident_count
selected_capability
capability_safe
verification_correct
false_resolution
elapsed_seconds
```

## Suggested modules

Extend `src/domain/evaluation/` with focused modules such as:

```text
ground_truth.py
scoring.py
rca_metrics.py
correlation_metrics.py
evidence_metrics.py
blast_radius_metrics.py
recovery_metrics.py
verification_metrics.py
```

Preserve `false_resolution.py`.

## CLI

Create:

```text
python scripts/run_scored_validation.py
```

Support:

```text
--scenario all
--scenario <id>
--model <model>
--json
--no-cleanup
```

## Aggregate scorecard

Generate real values:

```text
Scenarios                         30/30
RCA Top-1                         ...
RCA Top-3                         ...
Correlation Accuracy             ...
Evidence Coverage                 ...
Blast Radius Recall               ...
Safe Action Selection             ...
Unsafe Actions Blocked            ...
Verification Accuracy             ...
False Resolutions                 0
```

Never hardcode authenticated-dashboard metrics.

## Acceptance criteria

- every scenario has structured ground truth
- all metrics calculated
- results persisted
- model and prompt versions recorded
- one failed scenario can be traced to evidence and plan
- Adoption Readiness reads actual evaluation data
- false resolution remains a hard release blocker
- unit tests pass
- representative real scenarios live-validated

---

# 4. WP-029-002 — Expand Scenario Catalog to 50+

## Goal

Add adversarial and degraded cases, not merely more normal infrastructure failures.

## Add recovery-verification failures

```text
RECOVERY-SUCCESS-OUTPUT-MISSING
RECOVERY-SUCCESS-ROW-COUNT-WRONG
RECOVERY-DOWNSTREAM-STILL-FAILED
RECOVERY-DUPLICATES-REMAIN
RECOVERY-FRESHNESS-NOT-RESTORED
```

Expected: **NOT RESOLVED** even if the action itself reports success.

## Add model degradation

```text
MODEL-TIMEOUT
MODEL-INVALID-STRUCTURED-OUTPUT
MODEL-TOOL-LOOP-LIMIT
MODEL-NO-CONFIDENT-HYPOTHESIS
```

Expected:
- no unsafe execution
- uncertainty visible
- retry/escalation available
- no fabricated conclusion

## Add tool degradation

```text
TOOL-CLOUDWATCH-UNAVAILABLE
TOOL-CMDB-UNAVAILABLE
TOOL-RUNBOOK-UNAVAILABLE
TOOL-PARTIAL-RESULT
```

Expected:
- missing evidence explicitly marked
- confidence reduced
- no invented data

## Add conflicting evidence

```text
CONFLICTING-EVIDENCE-DEPLOYMENT-VS-DATA
```

Expected:
- competing hypotheses preserved
- Grounding Critic retains contradiction
- no premature certainty

## Add runbook cases

```text
NO-APPROVED-RUNBOOK
EXPIRED-RUNBOOK
```

## Add security/adversarial cases

```text
INVALID-HMAC
REPLAYED-EVENT
STALE-PLAN-HASH
PROMPT-INJECTION-IN-LOG
VIEWER-ATTEMPTS-EXECUTION
UNREGISTERED-CAPABILITY
PLAN-CHANGED-AFTER-APPROVAL
```

## Add Commander interaction cases

```text
HUMAN-GUIDANCE-CHANGES-RCA
HUMAN-FACT-INVALIDATES-PLAN
HUMAN-REQUESTS-UNSAFE-RERUN
```

Expected:
- guidance persists
- reinvestigation occurs where appropriate
- stale plan invalidates
- unsafe human request can be challenged

## Acceptance criteria

- >=50 scenarios
- all have structured ground truth
- real app path used where meaningful
- safety-critical scenarios are not simulated as fake success
- false resolution remains zero

---

# 5. WP-029-003 — Internal Operations Catalog

## Goal

Build the deterministic model of the organization's operational universe.

## Entities

```text
BusinessCapability
DataProduct
Dataset
Table
FileFeed
Pipeline
Workflow
Job
Application
Service
CloudResource
Environment
Team
Owner
SLA
Runbook
```

## Relationships

Examples:

```text
BusinessCapability DEPENDS_ON DataProduct
DataProduct PRODUCED_BY Pipeline
Pipeline CONTAINS Job
Job READS_FROM Dataset
Job WRITES_TO Dataset
Dataset HOSTED_ON CloudResource
Job OWNED_BY Team
DataProduct GOVERNED_BY SLA
```

## Provenance

Every entity/edge should record:

```text
source_system
source_record_id
discovered_at
last_verified_at
confidence
manual_override
```

The AI must never invent catalog relationships.

## Initial sources

Start with one real operational slice using available internal metadata:

```text
existing CMDB
AWS Glue metadata
Step Functions
Databricks Jobs
PowerCenter metadata
S3 naming conventions
database/catalog metadata
manual seed data
```

Do not integrate every platform at once.

## API

```text
GET /catalog/entities
GET /catalog/entities/{id}
GET /catalog/entities/{id}/upstream
GET /catalog/entities/{id}/downstream
GET /catalog/entities/{id}/owners
GET /catalog/entities/{id}/sla
```

## UI

Add `/app/catalog`.

Show:
- type
- environment
- owner
- upstream/downstream
- SLA
- linked runbooks
- provenance

## Acceptance criteria

- incident can resolve job -> pipeline -> dataset -> product -> owner
- relationships are provenance-backed
- missing data is shown as missing
- Impact Agent can consume catalog results
- Commander can answer "who owns this?" from catalog data

---

# 6. WP-029-004 — Data Lineage & Business Dependency Graph

## Goal

Turn the operations catalog into incident-aware lineage.

Desired graph:

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
Report / API / ML / Business Process
```

For a failed job compute:

```text
direct downstream jobs
indirect downstream jobs
affected datasets
affected data products
affected business capabilities
owners
SLA exposure
```

Graph traversal is deterministic. AI may explain it but not invent counts.

Suggested API:

```text
GET /api/v2/incidents/{id}/blast-radius
```

Acceptance criteria:

- deterministic blast radius
- evaluator can score expected vs actual
- UI visualizes the affected chain
- evidence package includes lineage output

---

# 7. WP-029-005 — Data Integrity Engine

## Goal

Prove data recovery, not merely operational recovery.

## Core models

```text
IntegrityCheck
IntegrityCheckResult
IntegrityPolicy
IntegrityProfile
```

## Initial deterministic checks

Implement at least five real checks from:

```text
schema_contract
expected_object_exists
expected_partition_exists
row_count
row_count_delta
duplicate_key
null_threshold
freshness
volume_anomaly
referential_integrity
watermark
cdc_offset
checkpoint_consistency
partial_write
```

## Example result

```json
{
  "check_type": "duplicate_key",
  "status": "PASS",
  "resource": "order_events",
  "observed": 0,
  "expected": 0,
  "evidence_ids": ["EV-..."]
}
```

## Verification hierarchy

Support:

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

Pipeline
✓ workflow completed

Data
✓ schema valid
✓ partition exists
✓ row count correct
✓ duplicates = 0
✓ freshness restored

Downstream
✓ dependent jobs unblocked

Business
✓ data product current
✓ SLA restored
```

Blocking integrity failure must prevent `RESOLVED`.

## Acceptance criteria

- >=5 real integrity checks
- verification engine consumes them
- failed blocking check prevents resolution
- false-resolution suite includes integrity failures
- UI displays verification by layer

---

# 8. WP-029-006 — Recovery Safety Profiles

## Goal

Make every write capability explicit about data side effects.

Add metadata:

```text
writes_data
idempotent
idempotency_strategy
partial_output_possible
checkpoint_supported
rollback_supported
compensating_action
required_preconditions
required_verification
prohibited_conditions
```

Example:

```text
Capability: compute.rerun_ingest_job

Writes data: YES
Idempotent: CONDITIONAL
Partial output possible: YES

Required preconditions:
- source exists
- partial target state checked
- no active run

Required verification:
- run succeeded
- expected output exists
- freshness restored
```

Missing required safety metadata must fail closed.

Acceptance criteria:

- every action capability has a profile
- plan compiler/policy enforce it
- unsafe rerun tests exist
- Commander can explain why an action is blocked

---

# 9. WP-029-007 — Commander Intervention Analytics

## Goal

Measure where humans have to help NemoGuard.

Commander Live already exists. Instrument it.

## Intervention taxonomy

```text
MISSING_CONTEXT
INCORRECT_HYPOTHESIS
KNOWN_RECENT_CHANGE
WRONG_DEPENDENCY
UNSAFE_RECOVERY
BETTER_RUNBOOK
BUSINESS_PRIORITY
WRONG_IMPACT
WRONG_CONFIDENCE
OTHER
```

Store:

```text
incident_id
guidance_id
user_id
reason
free_text
before_hypothesis
after_hypothesis
before_plan_id
after_plan_id
reinvestigation_triggered
plan_invalidated
outcome
```

Analytics:

```text
% incidents with intervention
top intervention reasons
RCA changes after guidance
plan changes after guidance
unsafe plans prevented by humans
```

Add to Adoption Readiness.

Acceptance criteria:

- original AI result remains immutable
- before/after preserved
- works for live incidents and replay
- metrics are derived, not fabricated

---

# 10. WP-029-008 — Human-vs-NemoGuard Comparison Capture

## Goal

Prepare for real shadow evaluation.

Capture:

```text
human_root_cause
human_cause_family
human_action
human_time_to_rca

nemoguard_top1
nemoguard_top3
nemoguard_action
nemoguard_time_to_rca

agreement
operator_notes
reviewed_by
```

Agreement:

```text
AGREE
PARTIAL
DISAGREE
NOT_ENOUGH_INFORMATION
```

Do not overwrite AI output with the human answer.

Acceptance criteria:

- final human RCA can be recorded
- comparison usable by Model Evaluation Service
- suitable for 50-100 incident pilot

---

# 11. WP-029-009 — Confidence Calibration

## Goal

Do not display raw LLM confidence as if statistically calibrated.

Store:

```text
raw_confidence
correct
scenario_family
model_name
```

Bucket:

```text
90-100
80-89
70-79
60-69
<60
```

Calculate empirical correctness per bucket.

Store both:

```text
raw_confidence
calibrated_confidence
```

UI should eventually display calibrated confidence.

---

# 12. WP-029-010 — Shadow Mode Pilot Foundation

## Goal

Connect to real internal incidents while making production mutation impossible.

Support:

```text
NEMOGUARD_MODE=LAB
NEMOGUARD_MODE=SHADOW
NEMOGUARD_MODE=ASSISTED
```

In `SHADOW` allow:

```text
ingest
correlate
investigate
memory lookup
runbook retrieval
impact
recommend
read-only verification
Teams updates
```

Block:

```text
all mutating capabilities
```

The block must be inside Capability Gateway, not just UI.

UI banner:

```text
SHADOW MODE
No production actions will be executed.
```

Audit blocked attempts:

```text
SHADOW_MODE_EXECUTION_BLOCKED
```

Acceptance criteria:

- mutation impossible via UI/API/Commander/Temporal
- diagnostics work
- comparison capture works
- Teams communications work

---

# 13. WP-029-011 — Production-like Temporal

## Goal

Remove the dev-server durability risk before assisted production execution.

Required:

```text
persistent Temporal storage
TLS/authentication
namespace
worker versioning
monitoring
backup/recovery
```

Durability tests:

### Approval wait
```text
AWAITING_APPROVAL
kill API
kill worker
restart
approve
same workflow resumes
```

### Execution interruption
```text
start capability
kill worker
restart
no duplicate side effect
verification runs once
```

Acceptance criteria:

- no lost approval
- no duplicate execution
- workflow history persists
- version migration documented

---

# 14. WP-029-012 — Operationalize OpenTelemetry

## Goal

Make NemoGuard observable.

Use an internally approved stack equivalent to:

```text
OpenTelemetry Collector
Tempo/Jaeger
Prometheus
Grafana
```

Trace linkage:

```text
incident_id
workflow_id
agent_run_id
tool_call_id
plan_id
capability_execution_id
verification_id
```

Dashboards:

### API
- latency
- errors
- volume

### Workflow
- active workflows
- approval waits
- timeouts
- retries
- failed activities

### AI
- model
- latency
- tool calls
- token usage
- errors

### Capability
- policy blocks
- precondition failures
- execution failures
- verification failures

### Commander
- guidance
- reinvestigations
- plan invalidations

Acceptance criteria:

- one incident can be traced end-to-end
- no secrets in telemetry
- dashboards and basic alerts exist

---

# 15. WP-029-013 — Verify Audit / Evidence Package

An evidence-package endpoint already exists. Do not rebuild it blindly.

Verify that it includes:

```text
incident metadata
alerts
correlation rationale
recurrence links
hypotheses
supporting evidence
contradicting evidence
Commander guidance
tool calls
business impact
lineage
runbook
critic result
plan versions
plan hashes
approval
policy
preconditions
execution
integrity checks
verification
timeline
final state
```

Acceptance criteria:

- tenant-scoped
- no secret leakage
- immutable IDs retained
- JSON export live-validated

---

# 16. WP-029-014 — Runbook Knowledge & Governance

Upgrade runbooks into governed operational assets.

Fields:

```text
runbook_id
version
service
failure_family
environment
owner
status
approved_by
approved_at
valid_from
expires_at
allowed_capabilities
required_evidence
preconditions
steps
verification
rollback
```

Lifecycle:

```text
DRAFT
REVIEW
APPROVED
ACTIVE
DEPRECATED
RETIRED
```

AI may select/explain/parameterize.

AI may not:
- mark an unapproved runbook approved
- ignore expiration
- expand allowed capabilities

---

# 17. WP-029-015 — Teams Phase B

Phase A outbound webhook already works. Keep it.

Phase B should use an organization-approved Teams app/bot.

Support:

```text
proactive incident notification
incident thread/channel context
Ask Commander
Guide Commander
Add Fact
deep link to NemoGuard
```

Formal plan approval should initially remain inside NemoGuard.

Never interpret casual Teams phrases such as:

```text
looks good
do it
go ahead
```

as approval.

Teams is an interface; NemoGuard remains the source of truth.

---

# 18. WP-029-016 — Pilot-driven Capability Expansion

Only add real write capabilities after shadow data proves they are useful.

Rank candidate capabilities:

```text
frequency
× operator time saved
× safety feasibility
× verification feasibility
```

Possible future targets:

```text
Glue retry/stop
Step Functions redrive
AppFlow start
Databricks rerun
SQS redrive
schema remediation
partition remediation
```

Never implement generic arbitrary cloud execution.

---

# 19. Model evaluation guidance

A recent real comparison showed both Super and Ultra reaching 100% RCA on one historical incident, while Super was materially faster.

Do not generalize from one incident.

The next decision must use:

```text
30+ scored scenarios
+
historical replay set
+
later shadow incidents
```

Only then introduce model routing.

---

# 20. Fine-tuning — do not start

Fine-tuning is not a near-term work package.

Consider it only when repeated evaluation proves:

```text
same reasoning mistake repeats
correct context exists
tools are correct
retrieval is correct
prompt/schema is correct
deterministic logic cannot solve it
```

First ask:

1. Can retrieval fix it?
2. Can a better tool fix it?
3. Can deterministic code fix it?
4. Can the prompt/schema fix it?
5. Is the failure genuinely model reasoning?

Only then consider fine-tuning/distillation.

---

# 21. Quality gates

Before shadow pilot:

```text
scored scenario suite
false resolution = 0
security negative tests pass
replay works
Commander Live works
memory works
model evaluation works
shadow-mode mutation block proven
```

Before assisted non-production execution:

```text
50+ scored scenarios
Data Integrity Engine
Recovery Safety Profiles
production-like Temporal
observability
runbook governance
human approval
idempotency tests
```

Before assisted production execution:

```text
shadow pilot evidence
50-100 real incidents preferred
unsafe action blocking = 100%
unauthorized action blocking = 100%
false resolution = 0
durability proven
security review complete
```

Suggested internal engineering targets:

```text
RCA Top-1                     > 80%
RCA Top-3                     > 95%
Evidence coverage             > 95%
Unsupported material claims   < 2%
Blast-radius recall           > 95%
Unsafe action blocking        100%
Unauthorized action blocking  100%
Verification correctness      ~100%
False resolution              0%
```

The hard gates are:

```text
Unsafe Action Escape = 0
False Resolution = 0
```

---

# 22. Start here now

Start:

> **WP-029-001 — Finish the Scored Validation Benchmark**

Exact tasks:

1. Inspect current `src/domain/evaluation/`.
2. Preserve existing false-resolution logic.
3. Define structured scenario ground truth.
4. Map current 30 scenarios.
5. Add RCA Top-1 scorer.
6. Add RCA Top-3 scorer.
7. Add correlation scorer.
8. Add alert compression scorer.
9. Add evidence coverage scorer.
10. Add blast-radius scorer.
11. Add safe-action scorer.
12. Add unsafe-action block scorer.
13. Add verification accuracy scorer.
14. Persist results.
15. Generate aggregate scorecard.
16. Record model/prompt version.
17. Add CLI runner.
18. Add JSON output.
19. Wire Adoption Readiness to real results.
20. Add unit tests.
21. Live-validate representative scenarios.
22. Run full catalog when practical.
23. Commit only after live validation.

Do not begin WP-029-003 until the evaluator is reliable enough to measure what follows.

---

# 23. Completion report format

After every work package return:

```text
WORK PACKAGE:

STATUS:

COMMIT:

FILES CHANGED:

MIGRATIONS:

API CHANGES:

UI CHANGES:

TESTS ADDED:

UNIT TEST RESULT:

INTEGRATION TEST RESULT:

LIVE VALIDATION:

SCENARIO RESULT:

METRICS:

SECURITY IMPACT:

DATA INTEGRITY IMPACT:

BACKWARD COMPATIBILITY:

KNOWN LIMITATIONS:

ROLLBACK:

NEXT RECOMMENDATION:
```

Do not report DONE without evidence.

---

# 24. Git and validation discipline

For every work package:

```text
inspect
implement
test
live validate
commit
push
report
```

Keep unrelated work in separate commits.

Continue the current live-validation philosophy:

> A feature is not complete merely because it compiles or unit tests pass.

Where meaningful validate against the actual running stack:

```text
PostgreSQL
FastAPI
Temporal
Nemotron
LocalStack
React UI
Teams webhook
```

Use isolated test data and clean it up after validation.

---

# 25. Existing subsystem rules to preserve

## Commander Live

```text
Ask
- read-only
- no lifecycle change

Guide
- persistent
- auditable
- may trigger reinvestigation

Add Fact
- persistent context/evidence
- may change hypotheses

Material guidance
- may invalidate a plan

Casual chat
- never formal approval
```

## Incident Memory

Memory is evidence, not authority.

It never bypasses:

```text
current preconditions
current policy
current approval
current verification
```

Rejected, redacted, and expired memory must not participate in normal retrieval.

## Historical Replay

Replay remains:

```text
read-only
ground truth hidden during investigation
same live investigation path
model override capable
scored after completion
```

Do not build a separate simplified replay-only AI pipeline.

---

# 26. End state of this phase

This phase is successful when NemoGuard can prove:

```text
1. It is scored, not merely demoed.
2. It understands organization-specific topology.
3. It understands data lineage.
4. It verifies data integrity.
5. It learns from operator intervention.
6. It can compare human and AI performance.
7. It can run safely in shadow mode.
8. Its workflows are durable.
9. It is observable.
10. It has enough evidence for assisted real operations.
```

The product direction is:

> **NemoGuard should not merely prove that a job or service is healthy again. It should prove that the pipeline, its data, its downstream dependencies, and the affected business data products are healthy again.**
