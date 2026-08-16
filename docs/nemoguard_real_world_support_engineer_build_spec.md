# NemoGuard Real-World Support Engineer Expansion Specification

**Audience:** AI coding agent, solution architect, backend engineer, platform engineer, security engineer, SRE, product manager, support operations lead, auditor, and enterprise administrator.

**Purpose:** Convert the current NemoGuard proof of concept into a production-grade agentic support engineering platform that can operate in highly complex, multi-domain, multi-application technology environments. This document is a build specification, not a concept note. It defines product behavior, architecture, data models, agent responsibilities, tool contracts, safety controls, user experiences, administration, auditability, evaluation, rollout, and acceptance criteria.

**Primary outcome:** NemoGuard should behave like a strong production support engineer within a clearly certified scope. It must observe systems, form and test hypotheses, correlate evidence, calculate technical and business impact, propose safe actions, obtain the required approval, execute deterministic tools, verify recovery independently, collaborate with people, preserve an auditable record, and learn from reviewed outcomes.

**Source basis:** `AGENT_CAPABILITIES_SNAPSHOT.md` supplied by the product owner, together with the current implementation summaries. The current-state statements in Section 1 must be revalidated against the repository before each major implementation phase.

## Table of contents

1. Current-state baseline
2. Product definition
3. What it means to match a support engineer
4. Non-negotiable engineering principles
5. Target operating model
6. Reference architecture
7. Agent architecture
8. Domain skill packs
9. Canonical evidence fabric
10. Hypothesis-driven investigation
11. Service, dependency, ownership, and change graph
12. Governed capability gateway
13. Policy, authorization, and approval
14. Verification and rollback
15. Institutional memory and knowledge governance
16. User experience requirements
17. Administration experience
18. Auditability and evidence chain
19. Security architecture
20. Multi-tenancy and deployment models
21. Data architecture
22. Event and API architecture
23. Connector and extension architecture
24. Model architecture and optimization
25. Performance, scalability, and cost optimization
26. Observability and operation of NemoGuard itself
27. Testing and evaluation strategy
28. Rollout and autonomy progression
29. Product roadmap
30. Detailed first 90-day implementation plan
31. Prioritized engineering backlog
32. Recommended repository structure
33. Representative Pydantic models
34. LangGraph investigation design
35. Temporal workflow design
36. Golden-path incident competency
37. Coding-agent implementation rules
38. Definition of done
39. Immediate next actions for the current codebase
40. Final architectural position

---

## 1. Current-state baseline

The current platform already contains useful foundations and should be evolved rather than discarded:

- Alert-driven multi-agent investigation.
- A Watcher Agent for classification, noise filtering, recovery-signal detection, and incident correlation.
- An RCA Agent for root-cause analysis.
- Impact and Runbook agents that operate in parallel.
- A Grounding Critic that can reject unsupported or unsafe plans.
- LangGraph for the investigation phase.
- Temporal for workflow durability and retries.
- NVIDIA Nemotron models accessed through an OpenAI-compatible API.
- A human approval gate.
- A separate execution and verification stage.
- Read tools for logs, CMDB context, runbooks, and a LocalStack-backed subset of AWS observability APIs.
- A partial write path for a hardcoded data-ingestion scenario.
- A relational incident domain model, Pydantic contracts, a policy-aware tool registry, and a FastAPI control plane.

The current gaps that this specification must resolve are:

1. The Watcher has no authoritative observation tools and reasons primarily from the webhook payload and active incident list.
2. RCA is too dependent on a narrow log source.
3. Impact analysis is based on a synthetic CMDB rather than a real service, dependency, ownership, and business-impact graph.
4. Runbook retrieval uses static seeded records rather than governed enterprise knowledge sources.
5. The Grounding Critic has no independent evidence tools.
6. Recovery actions are free-text proposals rather than typed, executable plans.
7. The generic execution path does not invoke registered action tools.
8. Most default execution behavior is simulated or records database status only.
9. Default verification can report success without independently checking the affected platform.
10. The write-tool allowlist is hardcoded to one job/table pair.
11. Most AWS integrations are read-only and LocalStack-only.
12. There is no general network, change, deployment, cost, data-warehouse, cross-account, or cross-region investigation capability.
13. Policy is still partly prompt-driven instead of being structurally enforced by code.
14. The system is optimized for a small AWS/data-pipeline lab rather than a heterogeneous enterprise estate.

Do not hide or cosmetically work around these gaps. The implementation must replace simulated behavior with deterministic, testable, policy-governed capabilities in controlled phases.

---

## 2. Product definition

NemoGuard is an **agentic production support engineering control plane**.

It is not merely:

- An alert dashboard.
- A chatbot over logs.
- A runbook recommender.
- A collection of LLM agents.
- A generic autonomous shell.
- A replacement for all human engineers.

It is a governed system that manages the complete support lifecycle:

```text
Signals and alerts
    -> normalize and deduplicate
    -> correlate into incidents
    -> establish ownership and severity
    -> plan an investigation
    -> gather authoritative evidence
    -> form and test competing hypotheses
    -> determine technical and business impact
    -> retrieve approved knowledge and runbooks
    -> produce a typed recovery plan
    -> evaluate policy and risk
    -> obtain human approval when required
    -> execute deterministic, allowlisted actions
    -> verify recovery independently
    -> rollback or escalate when verification fails
    -> communicate status
    -> preserve an immutable audit trail
    -> capture reviewed outcomes for future retrieval and evaluation
```

### 2.1 Initial product boundary

Do not begin with the claim that NemoGuard supports every technology. The first real product boundary should be:

> An agentic support engineer for AWS-hosted data pipelines and distributed applications that investigates across observability, dependency, change, identity, network, and business context, then performs human-approved, independently verified recovery.

Deeply support a limited set of incident classes before expanding coverage. Recommended first classes:

1. Lambda timeout or error spike.
2. ECS service failing to maintain desired task count.
3. Container OOM or crash loop after a deployment.
4. Step Functions failed execution.
5. SQS backlog or DLQ growth.
6. Missing or late S3 input.
7. Partial data write or idempotency failure.
8. Schema regression.
9. IAM access denied.
10. Secret rotation causing authentication failure.
11. RDS connection exhaustion or performance degradation.
12. Deployment regression.
13. Downstream API timeout.
14. Disabled or missed schedule.
15. Data-quality threshold breach.

Each incident class must be implemented as a complete competency, not merely as an extra prompt example.

---

## 3. What it means to match a support engineer

Do not use a vague global claim such as "human-level support engineer." Certify the product by domain, incident class, environment, action, and autonomy level.

### 3.1 Capability maturity levels

| Level | NemoGuard behavior | Human equivalent |
|---|---|---|
| L0 - Observe | Collects, normalizes, and organizes alerts, logs, metrics, traces, topology, and changes | Monitoring console |
| L1 - Triage | Deduplicates, correlates, calculates initial severity, identifies ownership, and routes incidents | First-line support |
| L2 - Diagnose | Investigates, ranks hypotheses, cites evidence, identifies root cause, and calculates impact | Experienced support engineer |
| L3 - Supervised Remediation | Produces executable plans, requests approval, executes approved actions, verifies, and rolls back | Senior support engineer |
| L4 - Bounded Autonomy | Automatically resolves certified, reversible, low-risk incident classes under policy | Automated operations engineer |
| L5 - Major Incident Coordination | Coordinates multiple teams, workstreams, decisions, communications, recovery, and handover | Incident commander |

### 3.2 Capability certification record

Store certification as data, for example:

```yaml
capability_id: aws.sqs.dlq_redrive
incident_class: SQS_DLQ_GROWTH
product_version: 1.8.0
environment_scope:
  - nonproduction
  - production
maturity_level: L3
autonomy_mode: HUMAN_APPROVAL_REQUIRED
supported_conditions:
  max_messages: 100
  message_age_minutes: 60
  idempotency_verified: true
forbidden_conditions:
  regulated_payload: true
  unknown_consumer_side_effects: true
evaluation:
  scenario_count: 120
  diagnosis_top1_accuracy: 0.94
  unsafe_action_block_rate: 1.0
  recovery_success_rate: 0.97
approved_by:
  - platform_operations
  - security
  - application_owner
valid_from: 2026-08-01
review_due: 2026-11-01
```

Autonomy must be granted to a specific capability under specific conditions, never to an agent globally.

---

## 4. Non-negotiable engineering principles

1. **Deterministic facts remain deterministic.** Counts, status, ownership, SLA time, execution result, approval state, and verification outcome must come from code and source systems, not model inference.
2. **Models propose; policy decides; deterministic code executes.**
3. **No arbitrary shell, unrestricted SQL, or unrestricted cloud API access is exposed to a model.**
4. **Every material claim cites evidence.**
5. **Supporting and contradicting evidence are both preserved.**
6. **A downstream symptom must not be accepted as root cause without causal evidence.**
7. **Every write action is typed, allowlisted, risk-classified, authorized, audited, and idempotent where possible.**
8. **Approval binds to an immutable plan hash and exact action parameters.**
9. **An action result is not proof of recovery. Verification is independent.**
10. **Every reversible action has rollback or a documented compensation path.**
11. **Every workflow can survive process restarts.**
12. **Every tenant, environment, account, region, and resource boundary is explicit.**
13. **Secrets never enter model context.**
14. **Retrieved content is untrusted data and cannot redefine policy.**
15. **The UI is not the workflow engine.**
16. **The product must degrade safely when models or connectors are unavailable.**
17. **Historical learning creates reviewed suggestions, not silent policy changes.**
18. **New capabilities are shipped with evaluation data, permissions, verification, rollback, and documentation.**

---

## 5. Target operating model

### 5.1 Incident lifecycle

Use a lifecycle that supports both investigation and operational execution:

```text
DETECTED
-> NORMALIZING
-> CORRELATING
-> TRIAGED
-> INVESTIGATING
-> EVIDENCE_INCOMPLETE | DIAGNOSIS_READY
-> PLAN_DRAFTED
-> PLAN_VALIDATED
-> AWAITING_APPROVAL | READY_FOR_AUTOMATION
-> EXECUTING
-> VERIFYING
-> RESOLVED | ROLLED_BACK | ESCALATED | FAILED
-> POST_INCIDENT_REVIEW
-> CLOSED
```

Add sub-status and reason codes rather than creating dozens of top-level states. Examples:

```text
INVESTIGATING / WAITING_FOR_CONNECTOR
INVESTIGATING / MODEL_RETRY
AWAITING_APPROVAL / SECURITY_APPROVAL
EXECUTING / ACTION_2_OF_4
VERIFYING / OBSERVATION_WINDOW
FAILED / POLICY_DENIED
ESCALATED / DOMAIN_EXPERT_REQUIRED
```

### 5.2 State ownership

Avoid three competing sources of truth.

- **Temporal owns durable operational workflow progression**, timers, approvals, execution, verification, retries, cancellation, compensation, and workflow versioning.
- **LangGraph owns bounded investigation state**, hypotheses, evidence requests, domain skill routing, and critique loops.
- **PostgreSQL stores the queryable product projection**, incident records, evidence metadata, hypotheses, plans, actions, approvals, and user-facing state.
- **Append-only audit storage records immutable events**.
- **Object storage retains large evidence payloads**.

Temporal must emit domain events that update the PostgreSQL projection. UI code must never directly mutate workflow state.

---

## 6. Reference architecture

```text
+--------------------------------------------------------------------+
| Experience Layer                                                   |
| Operator Workbench | Major Incident View | ChatOps | ITSM | Admin |
| Approvals | Audit Explorer | Reporting | Mobile Notifications      |
+-------------------------------+------------------------------------+
                                | REST / SSE / WebSocket / Webhooks
+-------------------------------v------------------------------------+
| Product Control Plane                                              |
| FastAPI/API Gateway | Identity | Tenancy | Incidents | Ownership    |
| Approvals | Knowledge | Capability Catalog | Policy Administration |
+------------------+-----------------------------+--------------------+
                   |                             |
+------------------v----------------+  +---------v-------------------+
| Durable Workflow Runtime         |  | Investigation Runtime        |
| Temporal                         |  | LangGraph                    |
| lifecycle, timers, approvals,    |  | supervisor, hypotheses,      |
| execution, verification,         |  | evidence selection, domain   |
| rollback, escalation             |  | analysis, critique, planning |
+------------------+---------------+  +---------+-------------------+
                   |                             |
                   +--------------+--------------+
                                  |
+---------------------------------v----------------------------------+
| Governed Capability Gateway                                         |
| Typed tool contracts | registry | authz | risk | policy | budgets   |
| rate limits | idempotency | audit | plan compiler | secret brokering|
+--------+-----------------------+----------------------+--------------+
         |                       |                      |
+--------v---------+  +----------v-----------+  +-------v------------+
| Evidence         |  | Context and Knowledge |  | Action Executors   |
| Connectors       |  | Connectors             |  | Cloud, data, app,  |
| logs, metrics,   |  | CMDB, catalog, wiki,   |  | ITSM, network,     |
| traces, changes  |  | runbooks, incidents    |  | deployment         |
+--------+---------+  +----------+------------+  +-------+------------+
         |                       |                       |
+--------v-----------------------v-----------------------v------------+
| Customer Trust Zones                                                 |
| AWS | Azure | GCP | Kubernetes | SaaS | On-prem | Data Platforms    |
| Customer-side connector runtime, short-lived credentials, mTLS       |
+-----------------------------------------------------------------------+

Supporting platform services:
PostgreSQL | object storage | event broker | Redis/cache | search/index
secrets manager | OpenTelemetry | analytics warehouse | feature flags
```

### 6.1 Recommended technology responsibilities

- **FastAPI:** public and internal APIs, authentication middleware, request validation, event delivery, and integration endpoints.
- **LangGraph:** bounded investigation and reasoning loops only.
- **Temporal:** durable operational lifecycle and long-running control flow.
- **PostgreSQL:** transactional system of record and queryable projections.
- **Object storage:** raw logs, large tool payloads, evidence snapshots, exported reports, and immutable audit bundles.
- **Event broker:** ingestion buffering, domain events, decoupling, backpressure, and replay.
- **Redis:** optional short-lived caching, rate limits, and distributed coordination; never the durable source of truth.
- **OpenTelemetry:** traces, metrics, logs, and context propagation.
- **Policy engine:** policy-as-code evaluation separate from model prompts.
- **Search/index:** hybrid lexical, metadata, vector, and graph-adjacent retrieval for knowledge and past incidents.

---

## 7. Agent architecture

Do not create one independent LLM agent per technology service. Use a central supervisor and domain skill packs.

### 7.1 Core logical agents

#### Watcher and Correlation Agent

Responsibilities:

- Validate webhook structure and provenance.
- Normalize vendor-specific alerts into a canonical signal model.
- Deduplicate repeated alerts.
- Determine whether the signal is noise, a new incident, an update to an incident, or a recovery signal.
- Call authoritative tools when the payload is ambiguous.
- Correlate using time, topology, change, error signature, resource identity, and causal relationships.
- Produce deterministic correlation features for the correlator engine.

The Watcher must not make final correlation decisions using only free-form LLM judgment. Use deterministic clustering plus model-assisted interpretation for ambiguous payloads.

#### Incident Supervisor

Responsibilities:

- Establish the investigation objective.
- Select domain skill packs.
- Maintain the hypothesis ledger.
- Allocate investigation budgets.
- Run independent domain analyses in parallel.
- Decide when evidence is sufficient.
- Request human clarification when necessary.
- Produce a structured diagnosis summary.

#### RCA Agent

Responsibilities:

- Generate competing causal hypotheses.
- Select the next evidence request based on expected information gain.
- Update confidence using supporting and contradicting evidence.
- Distinguish primary cause, contributing factor, trigger, and symptom.
- Return explicit unknowns and escalation conditions.

#### Impact Agent

Responsibilities:

- Traverse technical dependencies.
- Calculate affected resources and service paths.
- Map technical impact to business services, customers, SLAs, data products, and owners.
- Determine current and projected impact.
- Avoid LLM-generated counts; use graph queries and source systems.

#### Runbook and Knowledge Agent

Responsibilities:

- Retrieve only approved and in-scope runbooks.
- Consider environment, resource version, incident class, and effective dates.
- Identify expired or conflicting procedures.
- Adapt a runbook into abstract action intents without inventing executable tool names.
- Cite runbook version and owner.

#### Grounding and Safety Critic

Responsibilities:

- Independently verify material claims.
- Request additional evidence when citations are weak or contradictory.
- Ensure the plan addresses the cause rather than a symptom.
- Validate that required preconditions, approval, verification, and rollback are defined.
- Reject unsafe or non-executable plans.

Allowed outcomes:

```text
PASS
PASS_WITH_REDUCED_CONFIDENCE
MORE_EVIDENCE_REQUIRED
HUMAN_EXPERT_REQUIRED
PLAN_UNSAFE
PLAN_NOT_EXECUTABLE
POLICY_REVIEW_REQUIRED
```

The critic should use a separate model invocation and, for high-impact incidents, an independent evidence retrieval path.

#### Communication Agent

Responsibilities:

- Draft audience-specific updates for operators, executives, customers, and technical teams.
- Use only confirmed facts and clearly label estimates.
- Preserve incident timeline and action status.
- Never independently publish a high-impact communication without configured approval.

### 7.2 Deterministic services that are not LLM agents

These must remain deterministic services:

- Normalization.
- Deduplication.
- Correlation scoring.
- Graph traversal and blast-radius calculation.
- SLA countdown.
- Permission evaluation.
- Plan compilation.
- Tool resolution.
- Action execution.
- Idempotency enforcement.
- Verification.
- Rollback.
- Audit recording.
- Cost accounting.

---

## 8. Domain skill packs

A skill pack is the deployable and certifiable unit of support competence. It must include data contracts, diagnostic knowledge, tools, policies, verification, and tests.

### 8.1 Skill pack manifest

```yaml
skill_pack_id: aws.ecs.operations
version: 1.0.0
owner: cloud_runtime_team
status: certified
supported_resource_types:
  - AWS_ECS_SERVICE
  - AWS_ECS_TASK
supported_incident_classes:
  - ECS_DESIRED_COUNT_NOT_MET
  - ECS_OOM_LOOP
  - ECS_DEPLOYMENT_REGRESSION
required_read_capabilities:
  - aws.ecs.describe_service
  - aws.ecs.describe_tasks
  - aws.cloudwatch.query_metrics
  - aws.cloudwatch.query_logs
  - change.get_recent_deployments
  - graph.get_dependencies
optional_read_capabilities:
  - aws.xray.query_traces
  - network.test_reachability
allowed_action_intents:
  - RESTART_STATELESS_SERVICE
  - ROLLBACK_DEPLOYMENT
  - UPDATE_TASK_DEFINITION_RESOURCE_LIMIT
verification_policies:
  - VP-ECS-RECOVERY-003
escalation_conditions:
  - persistent_data_corruption_risk
  - unknown_side_effects
  - customer_managed_approval_required
permissions_manifest: permissions/aws_ecs_read_write.yaml
evaluation_suite: eval/aws_ecs_v1.jsonl
runbook_tags:
  - ecs
  - containers
  - deployment
```

### 8.2 Application and API operations skill pack

Coverage:

- HTTP 4xx/5xx spikes.
- Latency and saturation.
- Dependency timeouts.
- Thread, connection, and pool exhaustion.
- Cache failure.
- Feature-flag regression.
- Configuration mistakes.
- Third-party API degradation.
- Bad releases.

Evidence tools:

- Application logs.
- Metrics.
- Distributed traces.
- Endpoint health.
- Deployment history.
- Feature-flag history.
- Configuration diffs.
- Dependency graph.
- Synthetic transaction results.

Typical actions:

- Roll back an approved deployment.
- Restore a previous configuration version.
- Disable a feature flag.
- Restart a stateless workload.
- Scale within a bounded limit.
- Open or update an incident ticket.

### 8.3 Cloud runtime skill pack

Coverage:

- Lambda, ECS, EKS/Kubernetes, EC2, Auto Scaling, load balancers, serverless schedules, and capacity failures.

Evidence tools:

- Desired versus running state.
- Container termination reasons.
- CPU, memory, throttling, and concurrency.
- Pod and task events.
- Health checks.
- Scaling events.
- Image and task-definition changes.
- Instance status.
- Cluster capacity.

Typical actions:

- Retry an idempotent invocation.
- Force a new deployment of a stateless service.
- Roll back an application version.
- Restore a previous task definition.
- Restart a failed worker.
- Adjust scale within pre-approved bounds.

### 8.4 Data pipeline and integration skill pack

Coverage:

- Airflow, AWS Glue, Step Functions, Databricks, Kafka, S3 landing zones, dbt, Informatica, warehouse loads, ETL/ELT, and data-quality failures.

Evidence tools:

- DAG and execution state.
- Source-file arrival.
- Schema history.
- Row counts and checksums.
- Checkpoints and watermarks.
- Queue/topic lag.
- Data freshness.
- Data-quality results.
- Lineage.
- Warehouse query history.
- Recent code/configuration changes.

Typical actions:

- Retry an idempotent job.
- Resume or pause a schedule.
- Clean a scoped partial write after a dry run.
- Restore a previous schema mapping.
- Reprocess a bounded partition.
- Reset a checkpoint under an approved procedure.
- Redrive a bounded message set.

### 8.5 Database and storage skill pack

Coverage:

- PostgreSQL/RDS, Redshift, Snowflake, DynamoDB, object storage, connection exhaustion, locking, replication lag, storage pressure, and query degradation.

Evidence tools:

- Instance and cluster status.
- Sessions and locks.
- Query history.
- Storage, IOPS, CPU, and memory.
- Replication state.
- Schema and statistics.
- Backup and restore state.
- Capacity trends.

Typical actions:

- Terminate an approved blocking session under strict policy.
- Increase a connection pool at the application layer.
- Restore a previous parameter group.
- Scale within approved boundaries.
- Trigger maintenance or failover only with elevated approval.

### 8.6 Network and connectivity skill pack

Coverage:

- DNS, routes, security groups, NACLs, VPC endpoints, load balancers, certificates, proxies, firewalls, service mesh, and egress dependencies.

Evidence tools:

- Reachability analysis.
- Flow logs.
- Route and route-table inspection.
- DNS resolution.
- Certificate validity.
- Security-group and NACL comparison.
- Endpoint status.
- Proxy and mesh policy.
- Network change history.

Typical actions:

- Renew or replace an approved certificate.
- Restore a previous network policy version.
- Modify a rule only through a customer-approved runbook and elevated approval.
- Fail over to a predefined endpoint.

### 8.7 IAM and security skill pack

Coverage:

- Access denied, expired credentials, trust-policy errors, missing permissions, secret rotation, certificate expiration, and key-policy failures.

Evidence tools:

- IAM simulation.
- Role trust relationships.
- Access Analyzer.
- Authentication events.
- Secret metadata without secret values.
- KMS and resource policies.
- CloudTrail.
- Security findings.

Typical actions:

- Revert an approved policy version.
- Re-establish an approved trust relationship.
- Trigger secret rotation through a governed procedure.
- Refresh a workload credential.

Never place secret values into evidence summaries or model context.

### 8.8 Change intelligence skill pack

This is a cross-cutting priority because many incidents follow a change.

Coverage:

- Deployments.
- Configuration updates.
- Infrastructure-as-code changes.
- IAM modifications.
- Database migrations.
- Package updates.
- Feature flags.
- Scheduled maintenance.

Evidence tools:

- CloudTrail.
- AWS Config or equivalent inventory/configuration history.
- CI/CD systems.
- Git commits and pull requests.
- Deployment systems.
- Change tickets.
- Feature-flag audit records.
- Infrastructure drift.

Required output:

```json
{
  "change_id": "DEP-442",
  "change_type": "APPLICATION_DEPLOYMENT",
  "target_resources": ["svc-customer-profile"],
  "changed_at": "2026-08-05T09:42:00Z",
  "initiator": "codepipeline/prod",
  "summary": "Schema mapping changed loyalty_id to member_id",
  "incident_time_delta_seconds": 360,
  "causal_relevance_score": 0.91,
  "evidence_ids": ["EVD-101", "EVD-102"]
}
```

### 8.9 Cost and capacity skill pack

Coverage:

- Cost anomalies.
- Unexpected scaling.
- Runaway queries.
- Unbounded retries.
- Storage growth.
- Expensive remediation choices.

Evidence tools:

- Cost and usage data.
- Budgets.
- Resource utilization.
- Scaling history.
- Estimated action cost.

Before approving a scaling or rerun action, the policy layer should be able to check budget and estimated cost.

### 8.10 Business impact and ownership skill pack

Coverage:

- Business services.
- Customer journeys.
- Data products.
- SLAs and SLOs.
- Revenue or operational criticality.
- Regulatory impact.
- Owners and escalation paths.

Evidence tools:

- CMDB/service catalog.
- Business lineage.
- On-call schedules.
- SLA catalog.
- Customer-impact metrics.
- ITSM incidents and changes.

The LLM may explain the result, but all counts, owners, deadlines, and service relationships must be computed from source data.

---

## 9. Canonical evidence fabric

A real support engineer uses many evidence sources. Build a uniform evidence fabric so agents do not receive unstructured vendor payloads directly.

### 9.1 Evidence record

```json
{
  "evidence_id": "EVD-20260805-0182",
  "tenant_id": "TEN-001",
  "incident_id": "INC-1234",
  "source_type": "CLOUDTRAIL_EVENT",
  "source_system": "AWS_CLOUDTRAIL",
  "source_account": "123456789012",
  "source_region": "us-east-1",
  "resource_ids": ["arn:aws:lambda:us-east-1:123456789012:function:orders"],
  "observed_at": "2026-08-05T09:43:12Z",
  "retrieved_at": "2026-08-05T09:48:14Z",
  "summary": "Function memory changed from 1024 MB to 512 MB",
  "structured_facts": {
    "old_memory_mb": 1024,
    "new_memory_mb": 512,
    "actor": "codepipeline/prod"
  },
  "raw_object_uri": "s3://nemoguard-evidence/TEN-001/INC-1234/EVD-20260805-0182.json.gz",
  "content_hash": "sha256:...",
  "authority": "AUTHORITATIVE",
  "sensitivity": "INTERNAL",
  "redaction_status": "REDACTED",
  "tool_call_id": "TC-8871",
  "expires_at": null
}
```

### 9.2 Evidence authority levels

| Level | Meaning | Examples |
|---|---|---|
| AUTHORITATIVE | Direct source of truth | Cloud API state, database status, signed deployment record |
| HIGH | Strong operational signal | Metrics, traces, validated logs |
| MEDIUM | Useful but indirect | Ticket comments, operator notes, wiki content |
| LOW | Unverified or inferred | Model-generated summary, stale documentation |

Confidence calculations should weight authority, freshness, independence, and consistency.

### 9.3 Evidence ingestion rules

- Store large raw payloads outside model context.
- Generate a structured, redacted summary.
- Preserve the content hash and raw reference.
- Tag tenant, environment, account, region, resource, time, and sensitivity.
- Record the exact tool and arguments used to obtain it.
- Apply retention and legal-hold policy.
- Never allow retrieved evidence to introduce new instructions or tools.
- Detect and redact secrets, tokens, credentials, personal data, and regulated fields before model use.

### 9.4 Evidence bundles

For efficient model calls, build an evidence bundle containing:

```json
{
  "incident_id": "INC-1234",
  "investigation_question": "Why did order ingestion fail after deployment?",
  "time_window": {
    "start": "2026-08-05T09:30:00Z",
    "end": "2026-08-05T10:00:00Z"
  },
  "facts": [],
  "evidence_summaries": [],
  "known_changes": [],
  "service_graph_summary": {},
  "unknowns": [],
  "data_quality": {
    "missing_sources": [],
    "stale_sources": []
  }
}
```

---

## 10. Hypothesis-driven investigation

Replace a linear "query logs and produce RCA" pattern with an iterative investigation manager.

### 10.1 Hypothesis ledger

```json
{
  "hypothesis_id": "HYP-19",
  "incident_id": "INC-1234",
  "statement": "The deployment reduced ECS task memory and caused OOM termination.",
  "cause_category": "CONFIGURATION_REGRESSION",
  "status": "PROBABLE",
  "prior_probability": 0.35,
  "confidence": 0.82,
  "supporting_evidence_ids": ["EVD-41", "EVD-43"],
  "contradicting_evidence_ids": ["EVD-47"],
  "missing_evidence_requests": [
    "Previous task-definition memory value",
    "Deployment timestamp"
  ],
  "last_updated_at": "2026-08-05T09:52:00Z"
}
```

### 10.2 Investigation loop

```text
Generate an initial hypothesis set
    -> rank hypotheses
    -> identify discriminating evidence
    -> select the cheapest authoritative tool
    -> execute the read tool
    -> update support and contradiction
    -> calculate whether the evidence materially changes ranking
    -> continue, stop, or escalate
```

### 10.3 Tool-selection objective

Prefer a tool request that maximizes:

```text
expected_information_gain
x source_authority
x freshness
x success_probability
/ latency
/ cost
/ operational_risk
```

Do not call every tool for every incident.

### 10.4 Stop conditions

Stop investigation when one of the following applies:

- A probable cause exceeds the calibrated confidence threshold and has sufficient evidence coverage.
- Additional evidence is unlikely to change the decision.
- The investigation budget is exhausted.
- Required sources are unavailable.
- Contradictory evidence prevents a safe conclusion.
- The incident requires a domain expert.
- A policy requires human ownership.

When stopping without a conclusive diagnosis, return:

```text
Best current hypotheses
Supporting and contradicting evidence
Unknowns
Tools attempted
Unavailable sources
Recommended human team
Next-best manual check
Operational risk of waiting
```

### 10.5 Confidence calibration

Do not accept raw model confidence as calibrated probability. Build a calibration service using evaluated scenarios.

Inputs may include:

- Model-reported confidence.
- Evidence authority.
- Evidence coverage.
- Number of independent sources.
- Contradictions.
- Missing mandatory evidence.
- Incident-class historical performance.
- Similar-case agreement.
- Tool failure rate.

Output should include:

```json
{
  "raw_model_confidence": 0.93,
  "calibrated_confidence": 0.78,
  "confidence_band": "MEDIUM_HIGH",
  "reasons": [
    "Two authoritative evidence sources agree",
    "Deployment history supports the hypothesis",
    "Network evidence is unavailable"
  ]
}
```

---

## 11. Service, dependency, ownership, and change graph

A complex enterprise cannot be represented as a flat job dependency table.

### 11.1 Node types

- Business service.
- Customer journey.
- Application.
- Microservice.
- API.
- Batch job.
- Pipeline.
- Dataset.
- Database.
- Queue and topic.
- Compute resource.
- Cloud account and subscription.
- Region and environment.
- Network and endpoint.
- IAM role and service identity.
- Secret or certificate metadata.
- Dashboard and report.
- External dependency.
- Team and person.
- On-call rotation.
- Runbook.
- Deployment.
- Configuration version.
- Change record.
- SLO, SLA, and maintenance window.

### 11.2 Relationship types

```text
DEPENDS_ON
CALLS
READS_FROM
WRITES_TO
CONSUMES_FROM
PUBLISHES_TO
RUNS_ON
ASSUMES_ROLE
USES_SECRET
ROUTES_THROUGH
DEPLOYED_BY
CHANGED_BY
OWNED_BY
SUPPORTS
SERVES
GOVERNED_BY
MONITORED_BY
HAS_RUNBOOK
HAS_SLO
AFFECTS
PRECEDED
CORRELATED_WITH
```

### 11.3 Graph query examples

```text
Find all business services reachable downstream from a failed resource.
Find the nearest authoritative owner for a resource.
Find changes to any node within two dependency hops during the 30 minutes before failure.
Find all affected customer journeys with an SLA deadline in the next hour.
Find the common upstream ancestor of a set of alerts.
Find a healthy redundant path or failover target.
```

### 11.4 Storage strategy

Start with PostgreSQL tables and recursive queries, plus denormalized graph projections for common traversals. Add a dedicated graph database only when measured query complexity, traversal latency, or scale justifies it.

Every resource identity must include tenant, environment, provider, account/subscription/project, region, resource type, and canonical resource ID.

---

## 12. Governed capability gateway

The capability gateway is the only path through which agents, workflows, UI users, and integrations can access operational tools.

### 12.1 Gateway responsibilities

- Resolve abstract capability requests to tenant-enabled implementations.
- Validate typed input and output schemas.
- Enforce tenant, environment, account, region, resource, and user boundaries.
- Obtain short-lived credentials.
- Redact secrets and sensitive payloads.
- Apply risk classification and policy-as-code.
- Enforce rate limits, budgets, and concurrency controls.
- Generate idempotency keys.
- Record tool-call audit events.
- Store large results as evidence objects.
- Handle retries and timeouts.
- Return structured error codes.
- Prevent models from accessing disabled tools.

### 12.2 Capability registry record

```yaml
capability_id: aws.stepfunctions.redrive_execution
version: 1.2.0
kind: ACTION
provider: AWS
resource_types:
  - AWS_STEP_FUNCTION_EXECUTION
input_schema: schemas/aws/stepfunctions/redrive_input.json
output_schema: schemas/aws/stepfunctions/redrive_output.json
required_permissions:
  - states:RedriveExecution
risk_level: MEDIUM
allowed_environments:
  - development
  - test
  - production
supports_dry_run: true
idempotency: EXTERNAL_AND_INTERNAL
concurrency_policy: ONE_PER_TARGET
approval_policy: SINGLE_OPERATOR
precondition_policy: PP-STEPFUNCTIONS-REDRIVE-01
verification_policy: VP-STEPFUNCTIONS-REDRIVE-01
rollback_policy: null
executor: connectors.aws.stepfunctions.redrive_execution
owner: data_platform_operations
status: ACTIVE
```

### 12.3 Read-tool contract

```json
{
  "request_id": "REQ-123",
  "tenant_id": "TEN-001",
  "incident_id": "INC-1234",
  "capability_id": "aws.cloudwatch.query_metrics",
  "arguments": {
    "resource_id": "arn:aws:lambda:...",
    "metric_names": ["Errors", "Duration"],
    "start_time": "2026-08-05T09:30:00Z",
    "end_time": "2026-08-05T10:00:00Z"
  },
  "purpose": "Discriminate timeout from invocation failure",
  "budget_context": {
    "remaining_tool_calls": 12,
    "remaining_cost_units": 80
  }
}
```

Response:

```json
{
  "tool_call_id": "TC-8871",
  "status": "SUCCESS",
  "summary": "Error rate increased from 0.2% to 18.4% after 09:42 UTC.",
  "structured_facts": {},
  "evidence_ids": ["EVD-101"],
  "duration_ms": 218,
  "cost_units": 2,
  "warnings": []
}
```

### 12.4 Action-intent contract

The model should propose an abstract operational intent, not a function name:

```json
{
  "intent_type": "RETRY_FAILED_WORKFLOW",
  "target": {
    "resource_type": "AWS_STEP_FUNCTION_EXECUTION",
    "resource_id": "arn:aws:states:us-east-1:123456789012:execution:orders:abc"
  },
  "reason": "The original failure was caused by a resolved transient dependency.",
  "parameters": {
    "input_source": "ORIGINAL_EXECUTION"
  },
  "evidence_ids": ["EVD-201", "EVD-202"],
  "expected_effect": "The workflow completes without duplicating external side effects."
}
```

### 12.5 Plan compiler

The deterministic Plan Compiler must:

1. Validate the intent schema.
2. Resolve the target resource.
3. Select a registered tenant-enabled capability.
4. Load capability version, permissions, risk, preconditions, approval, verification, and rollback.
5. Validate environment and resource scope.
6. Fill safe deterministic defaults.
7. Reject unknown or ambiguous targets.
8. Create exact typed action steps.
9. Calculate blast radius and cost estimate.
10. Generate a canonical plan representation and plan hash.

Compiled action:

```json
{
  "action_id": "ACT-001",
  "sequence": 1,
  "capability_id": "aws.stepfunctions.redrive_execution",
  "capability_version": "1.2.0",
  "target": {
    "tenant_id": "TEN-001",
    "environment": "production",
    "account_id": "123456789012",
    "region": "us-east-1",
    "resource_id": "arn:aws:states:..."
  },
  "arguments": {
    "execution_arn": "arn:aws:states:..."
  },
  "risk_level": "MEDIUM",
  "preconditions": [
    "execution_status == FAILED",
    "failure_category == TRANSIENT",
    "side_effect_safety_check == PASSED"
  ],
  "approval_policy": "SINGLE_OPERATOR",
  "idempotency_key": "TEN-001:INC-1234:PLAN-3:ACT-001",
  "verification_policy_id": "VP-STEPFUNCTIONS-REDRIVE-01",
  "rollback_policy_id": null,
  "expected_effect": "Execution completes successfully.",
  "evidence_ids": ["EVD-201", "EVD-202"]
}
```

### 12.6 Generic execution engine

Replace all free-text and hardcoded action paths with a generic engine.

Execution sequence:

```text
Receive approved plan
    -> validate plan hash and approval validity
    -> acquire target-scoped concurrency lock
    -> refresh authorization and policy decision
    -> refresh all preconditions
    -> execute dry run where supported
    -> persist dry-run result
    -> execute capability using short-lived credentials
    -> persist exact request and response metadata
    -> emit action event
    -> run independent verification policy
    -> continue, compensate, rollback, or escalate
```

Required execution behavior:

- Exactly-once business behavior where practical; at-least-once invocation must be made safe through idempotency.
- Per-action timeout and retry policy.
- Circuit breaker for failing connectors.
- Cancellation support.
- Partial-success handling.
- Compensating actions.
- Resource-scoped locks.
- Action-level status and error codes.
- No success status based only on a returned HTTP 2xx.

### 12.7 Tool classes and default policy

| Class | Examples | Default policy |
|---|---|---|
| READ_ONLY | Logs, metrics, describe resource | Automatic within entitlement |
| OBSERVATIONAL_ACTIVE | DNS test, synthetic request | Automatic with rate limits |
| REVERSIBLE_LOW_RISK | Retry idempotent job, restart stateless worker | Human approval initially; eligible for certified autonomy |
| CONTROLLED_WRITE | Pause schedule, redrive DLQ, force deployment | Human approval |
| HIGH_IMPACT | Database failover, network policy change, broad rollback | Dual approval and change controls |
| DESTRUCTIVE | Delete production data, arbitrary resource deletion | Prohibited by default; exceptional break-glass only |

---

## 13. Policy, authorization, and approval

### 13.1 Policy must be structural

Prompt instructions are not policy enforcement. Evaluate policy outside the model and enforce it in the gateway and workflow.

Policy inputs should include:

```text
Tenant
User and groups
Role
Environment
Incident severity
Capability and version
Target resource
Risk class
Data classification
Change window
Maintenance window
Current system state
Cost estimate
Blast radius
Approval history
Plan hash
Model confidence and evidence coverage
Capability certification status
```

Policy decisions should include:

```json
{
  "decision": "REQUIRE_APPROVAL",
  "policy_version": "POL-2026.08.4",
  "required_approver_roles": ["PRODUCTION_OPERATOR"],
  "minimum_approvals": 1,
  "expires_in_minutes": 20,
  "constraints": {
    "max_messages": 100,
    "must_run_dry_run": true
  },
  "reasons": [
    "Production environment",
    "Medium-risk write capability"
  ]
}
```

### 13.2 Identity and permissions

Support:

- OIDC and SAML SSO.
- SCIM provisioning.
- Service accounts and workload identities.
- RBAC plus attribute-based restrictions.
- Just-in-time elevation.
- Break-glass access.
- Separation of duties.
- Environment-specific permissions.
- Customer-managed approver groups.

Recommended product roles:

| Role | Core permissions |
|---|---|
| Operator | Investigate, annotate, request plans, execute approved low/medium actions |
| Incident Commander | Coordinate incidents, assign owners, approve communications, manage workstreams |
| Approver | Approve defined risk classes within assigned environments |
| Domain Engineer | Add evidence, correct hypotheses, author technical recommendations |
| Runbook Author | Create and update runbooks but not approve own production changes |
| Runbook Approver | Approve and publish runbooks |
| Connector Administrator | Configure and test connectors and credentials |
| Policy Administrator | Configure risk and approval policy |
| Model Administrator | Manage model routing and prompt versions |
| Tenant Administrator | Manage users, environments, retention, and tenancy settings |
| Auditor | Read immutable evidence, decisions, approvals, and execution records |
| Read-only Executive | View impact, status, and outcome summaries |

### 13.3 Approval integrity

An approval record must bind to:

```text
Tenant ID
Incident ID
Plan ID and version
Plan hash
Exact action IDs and parameters
Target resources
Risk level
Policy version
Approver identity and role
Approval decision
Approval comments
Timestamp
Expiration
Authentication context
```

If any compiled action, parameter, target, risk, or policy changes, invalidate the approval.

Support:

- Approve entire plan.
- Approve individual actions.
- Reject.
- Request revision.
- Add conditions.
- Escalate for second approval.
- Withdraw approval before execution.

---

## 14. Verification and rollback

### 14.1 Independent verification principle

An action executor cannot verify itself. A cloud API returning success only confirms request acceptance, not recovery.

Verification must use independent postconditions such as:

- Resource reaches expected state.
- Error rate returns below threshold.
- Latency returns within SLO.
- Queue backlog decreases.
- Workflow succeeds.
- Required schema and row count are correct.
- Downstream services recover.
- Synthetic transactions pass.
- No new critical alerts occur during an observation window.

### 14.2 Verification policy

```json
{
  "verification_policy_id": "VP-ECS-RECOVERY-003",
  "version": "1.1.0",
  "checks": [
    {
      "check_id": "CHECK-1",
      "capability_id": "aws.ecs.get_service_health",
      "assertion": "running_count == desired_count",
      "timeout_seconds": 300
    },
    {
      "check_id": "CHECK-2",
      "capability_id": "aws.cloudwatch.query_metrics",
      "assertion": "error_rate_percent < 1.0",
      "observation_window_seconds": 600
    },
    {
      "check_id": "CHECK-3",
      "capability_id": "synthetic.call_endpoint",
      "assertion": "http_status == 200",
      "sample_count": 5
    }
  ],
  "minimum_required_checks": 3,
  "on_failure": "ROLLBACK_OR_ESCALATE"
}
```

### 14.3 Verification result

```json
{
  "verification_run_id": "VR-101",
  "action_id": "ACT-001",
  "status": "FAILED",
  "started_at": "2026-08-05T10:02:00Z",
  "completed_at": "2026-08-05T10:12:00Z",
  "checks": [
    {
      "check_id": "CHECK-1",
      "status": "PASSED",
      "evidence_ids": ["EVD-701"]
    },
    {
      "check_id": "CHECK-2",
      "status": "FAILED",
      "observed": 7.8,
      "expected": "<1.0",
      "evidence_ids": ["EVD-702"]
    }
  ],
  "recommended_next_state": "ROLLED_BACK"
}
```

### 14.4 Rollback and compensation

Every action must declare one of:

- `REVERSIBLE` with a tested rollback capability.
- `COMPENSATABLE` with a compensating workflow.
- `IRREVERSIBLE` with elevated policy and explicit risk acceptance.
- `NO_CHANGE` for read-only operations.

Rollback must be treated as a first-class action plan with its own policy, execution, and verification.

### 14.5 Observation windows

Some recoveries require time to stabilize. Temporal should own the observation timer and resume verification after the configured window. Do not keep an API request or UI session open.

---

## 15. Institutional memory and knowledge governance

### 15.1 Incident working memory

Store the complete current case:

- Signals and alerts.
- Normalization results.
- Correlation decisions.
- Timeline.
- Evidence.
- Hypotheses.
- Tool calls.
- Decisions.
- Owners.
- Approvals.
- Actions.
- Verification.
- Communications.
- Human corrections.

### 15.2 Long-term case memory

Store reviewed historical records:

- Incident signature.
- Confirmed root cause.
- Contributing factors.
- Successful and unsuccessful actions.
- Environment and resource context.
- Resolution time.
- Engineer feedback.
- Postmortem.
- Recurrence.

Use hybrid retrieval:

- Structured metadata filtering.
- Error-signature matching.
- Time-series pattern similarity.
- Graph similarity.
- Semantic retrieval.
- Environment and version weighting.

Do not treat a vector result as an authoritative fact. Historical cases are suggestions supported by references.

### 15.3 Curated organizational knowledge

Support governed content from:

- Runbooks.
- Architecture documents.
- Service catalogs.
- Known-error databases.
- Maintenance procedures.
- Escalation policies.
- Change calendars.
- Data classifications.
- Vendor support documents.

Each knowledge item must have:

```text
Owner
Version
Approval status
Source URI
Effective date
Expiry/review date
Environment scope
Applicable resource types
Incident-class tags
Last validation date
Sensitivity
```

### 15.4 Feedback workflow

Human feedback should create reviewed updates:

- Correct root cause.
- Add or remove evidence.
- Mark recommendation useful or unsafe.
- Propose a runbook change.
- Propose a correlation rule.
- Propose a capability certification update.

Never let the model silently modify policy, runbooks, or autonomy thresholds from a single incident.

---

## 16. User experience requirements

The product must support different operational roles. Do not design one dashboard for everyone.

### 16.1 Operator workbench

The primary incident screen must answer, within seconds:

- What is broken?
- How serious is it?
- Is the impact increasing or recovering?
- What is the current best diagnosis?
- What evidence supports or contradicts it?
- What remains unknown?
- What did the agents do?
- What action is recommended?
- What risk and approval are required?
- What is executing now?
- Has recovery been independently verified?

Recommended layout:

```text
+------------------------------------------------------------------------+
| Incident header                                                        |
| severity | state | owner | duration | SLA countdown | affected service |
+------------------------------------------------------------------------+
| Lifecycle stepper and current workflow status                          |
+------------------------------+-----------------------------------------+
| Investigation workspace      | Recovery and approval panel             |
| - hypotheses                 | - typed action sequence                 |
| - evidence                   | - exact targets and parameters          |
| - agent/tool activity        | - risk and policy decision              |
| - causal timeline            | - verification and rollback             |
+------------------------------+-----------------------------------------+
| Technical graph | Business impact | Timeline | Audit | Raw evidence    |
+------------------------------------------------------------------------+
```

Operator actions:

- Add evidence.
- Mark evidence irrelevant.
- Correct resource identity.
- Ask the agent to investigate a specific hypothesis.
- Add a hypothesis.
- Reject or reduce confidence in a hypothesis.
- Request more evidence.
- Request a revised plan.
- Approve or reject individual actions.
- Stop execution.
- Trigger rollback where policy permits.
- Assign or transfer ownership.
- Escalate to a domain team.
- Record the confirmed root cause.
- Rate the diagnosis and recovery.

### 16.2 Evidence experience

Every claim must be clickable. The evidence panel should show:

- Evidence summary.
- Source and authority.
- Observation and retrieval times.
- Resource identity.
- Exact tool call.
- Redaction status.
- Raw source link, subject to permission.
- Supporting or contradicting relationship.

Do not expose internal model chain-of-thought. Show observable agent actions, tool calls, structured conclusions, and evidence.

### 16.3 Hypothesis experience

Display a ranked hypothesis table:

| Hypothesis | Calibrated confidence | Supporting evidence | Contradictions | Status |
|---|---:|---:|---:|---|
| Deployment reduced task memory and caused OOM | 82% | 4 | 1 | Probable |
| Downstream database connection exhaustion | 31% | 1 | 3 | Unlikely |
| Network policy blocked egress | 12% | 0 | 2 | Rejected |

Show why confidence changed over time.

### 16.4 Recovery approval experience

An approver must see:

- Plain-language intent.
- Exact compiled capability and version.
- Exact target resources.
- Exact parameters.
- Evidence and reason.
- Preconditions and their current status.
- Risk classification.
- Blast radius.
- Estimated cost.
- Expected effect.
- Verification plan.
- Rollback or compensation.
- Plan hash and approval expiration.

Support action-level approval rather than forcing approval of an entire large plan.

### 16.5 Execution experience

Display live deterministic progress:

```text
PASSED   Approval and plan hash validated
PASSED   Preconditions refreshed
PASSED   Dry run completed
RUNNING  Restore task definition revision 44
PENDING  Force new deployment
PENDING  Verify task health for 10 minutes
PENDING  Verify API error rate
```

On failure, show the exact failed step, error class, retry status, and rollback decision.

### 16.6 Major incident mode

For high-severity, multi-domain incidents, provide:

- Incident commander assignment.
- Multiple workstreams.
- Domain owners.
- Decision log.
- Action items.
- Stakeholder and customer communications.
- Status cadence and reminders.
- Bridge or meeting links.
- Current impact statement.
- Recovery options and risks.
- Handover.
- Post-incident timeline export.

The Incident Supervisor may coordinate workstreams, but it must not collapse distinct faults into a single unsupported root cause.

### 16.7 Shift handover

Generate a structured handover:

```text
Current state
Confirmed facts
Probable hypotheses
Contradictions and unknowns
Actions completed
Actions in progress
Actions awaiting approval
Risks
Customer and business impact
Next checkpoint
Assigned owners
Escalation contacts
```

Every handover statement must cite incident records.

### 16.8 ChatOps and ITSM

Provide controlled interfaces for Teams, Slack, ServiceNow, Jira Service Management, or equivalent.

Supported commands should be explicit and permission-aware, for example:

```text
/incident status INC-1234
/incident evidence INC-1234
/incident investigate INC-1234 network
/incident approve PLAN-9 ACT-2
/incident reject PLAN-9 reason="Need database owner review"
```

A chat channel is an interface, not the source of truth. All commands must call the control-plane API and be audited.

### 16.9 Accessibility and usability

- WCAG-oriented keyboard navigation and semantic labels.
- Do not communicate severity by color alone.
- Support high-density operations views.
- Support time zones and localized timestamps.
- Preserve technical detail without forcing users to read raw JSON.
- Provide clear empty, loading, unavailable, denied, and failed states.
- Never render database `None` values directly.

---

## 17. Administration experience

### 17.1 Tenant and environment administration

Administrators must manage:

- Organizations and tenants.
- Business units.
- Environments.
- Cloud accounts, subscriptions, projects, clusters, and regions.
- Data residency.
- Retention.
- Encryption keys.
- Feature flags.
- Product version and release channel.

### 17.2 Connector administration

For every connector show:

- Status and last successful heartbeat.
- Configuration version.
- Granted permissions.
- Missing required permissions.
- Credential expiration.
- Region/account coverage.
- Read and write capabilities enabled.
- Rate-limit state.
- Last error.
- Test connection action.
- Data-volume and cost metrics.

Provide a permission analyzer that compares required permissions from enabled skill packs with actual connector permissions.

### 17.3 Capability administration

Administrators must be able to:

- Enable or disable skill packs.
- Enable or disable individual capabilities.
- Restrict capabilities by environment and resource tag.
- Configure action limits.
- Configure autonomy levels.
- Review capability certification evidence.
- View capability owner and version.
- Schedule recertification.
- Roll back a capability version.

### 17.4 Policy administration

Provide versioned policy configuration for:

- Risk classes.
- Approval requirements.
- Separation of duties.
- Change windows.
- Maintenance windows.
- Cost and scale limits.
- Regulated resources.
- Prohibited capabilities.
- Break-glass process.
- Autonomous execution thresholds.

Every policy change must be reviewed, versioned, tested, and audited.

### 17.5 Model and prompt administration

Manage:

- Model providers.
- Model routing by task.
- Customer-managed models.
- Data residency restrictions.
- Prompt and graph versions.
- Structured-output schemas.
- Token and cost budgets.
- Evaluation results.
- Rollback.
- Disabled providers.

A prompt or model change must go through offline evaluation and staged rollout before production use.

### 17.6 Knowledge and runbook administration

Support:

- Source connectors.
- Ingestion schedules.
- Document ownership.
- Approval workflow.
- Effective and review dates.
- Version comparison.
- Expiration alerts.
- Applicability tags.
- Conflicts.
- Retrieval quality metrics.

A runbook author must not be able to self-approve a high-impact production procedure unless explicitly allowed by policy.

### 17.7 Evaluation administration

Show per-domain and per-incident-class metrics:

- Diagnosis accuracy.
- Evidence coverage.
- Tool-selection accuracy.
- Unsafe-action block rate.
- Recovery success.
- Human correction rate.
- Cost and latency.
- Drift.

Provide a release gate that blocks capability promotion when required thresholds fail.

---

## 18. Auditability and evidence chain

### 18.1 Audit principles

- Append-only.
- Tenant-scoped.
- Time-synchronized.
- Tamper-evident.
- Searchable by incident, actor, model run, tool call, resource, policy, and approval.
- Exportable.
- Subject to retention and legal hold.
- Separate from mutable user-facing projections.

### 18.2 Audit event schema

```json
{
  "audit_event_id": "AUD-20260805-000991",
  "tenant_id": "TEN-001",
  "occurred_at": "2026-08-05T10:01:22.113Z",
  "event_type": "ACTION_APPROVED",
  "actor_type": "USER",
  "actor_id": "user-0091",
  "actor_roles": ["PRODUCTION_OPERATOR"],
  "incident_id": "INC-1234",
  "workflow_id": "temporal:INC-1234",
  "plan_id": "PLAN-9",
  "action_id": "ACT-2",
  "resource_ids": ["arn:aws:ecs:..."],
  "policy_version": "POL-2026.08.4",
  "plan_hash": "sha256:...",
  "decision": "APPROVED",
  "request_correlation_id": "CORR-8821",
  "metadata": {},
  "previous_event_hash": "sha256:...",
  "event_hash": "sha256:..."
}
```

### 18.3 Required audit event types

- Alert received, normalized, deduplicated, and correlated.
- Incident created, merged, split, reclassified, and closed.
- Agent run started and completed.
- Model request and structured response validated.
- Evidence requested, retrieved, redacted, accessed, and expired.
- Hypothesis created, updated, rejected, and confirmed.
- Tool request, policy decision, execution, retry, failure, and result.
- Plan compiled, validated, revised, and invalidated.
- Approval requested, granted, rejected, expired, and withdrawn.
- Action started, completed, failed, cancelled, and compensated.
- Verification started, passed, failed, and timed out.
- Rollback started and completed.
- Human correction and feedback.
- Runbook, policy, capability, connector, and model configuration change.
- Break-glass access.
- Audit export.

### 18.4 Model audit record

Record separately from user-visible explanation:

```text
Provider
Model identifier
Model deployment/endpoint
Prompt template version
LangGraph version and node
Structured-output schema version
Input evidence IDs
Redaction policy version
Output hash
Token usage
Latency
Cost
Validation result
Retries and fallback
Safety result
```

Do not store hidden chain-of-thought. Store structured rationale, evidence references, and decision outputs.

### 18.5 Tamper evidence

Consider:

- Hash chaining of audit events.
- Periodic signed integrity manifests.
- Object-lock or write-once audit archives.
- Customer export to a SIEM or immutable storage account.

---

## 19. Security architecture

### 19.1 Threat model

Cover at minimum:

- Cross-tenant data leakage.
- Prompt injection through logs, tickets, wiki pages, or runbooks.
- Tool abuse.
- Privilege escalation.
- Approval replay.
- Plan substitution after approval.
- SSRF through connectors.
- Secret exfiltration.
- Malicious or compromised connector.
- Model provider compromise.
- Supply-chain compromise.
- Audit tampering.
- Denial of service and denial of wallet.
- Unsafe autonomous remediation.
- Human social engineering through generated communications.

### 19.2 Retrieved content is untrusted

Maintain explicit channels:

```text
System policy
Developer/application instruction
Approved capability schemas
Retrieved evidence
User comments
External document content
```

Retrieved content may contain text such as "ignore previous rules". It must be treated only as data.

### 19.3 Credential architecture

- Use short-lived credentials.
- Separate read and action identities.
- Scope permissions by tenant, environment, account, region, service, and resource tags.
- Use customer-side execution for sensitive environments.
- Use outbound-only mTLS from customer connector runtimes where possible.
- Do not store broad permanent customer credentials centrally.
- Rotate credentials.
- Support emergency revocation.
- Record credential identity and role session, never secret values.

### 19.4 Data protection

- Encrypt in transit and at rest.
- Support customer-managed keys where required.
- Classify evidence.
- Redact secrets, credentials, personal data, and regulated fields.
- Enforce purpose-limited access.
- Implement retention and deletion workflows.
- Support regional storage and processing.
- Allow customers to prevent selected evidence classes from being sent to external models.

### 19.5 Secure tool execution

- Tool schemas are fixed and versioned.
- Validate all inputs.
- Prevent command injection.
- Use allowlisted SQL templates or read-only query services.
- Enforce statement timeouts and row limits.
- Block arbitrary file paths and URLs.
- Use egress allowlists.
- Sandbox custom extensions.
- Sign connector and skill-pack artifacts.

### 19.6 Break-glass

Break-glass execution must require:

- Explicit reason.
- Strong re-authentication.
- Elevated role.
- Time-limited access.
- Additional notification.
- Full audit.
- Mandatory post-event review.

---

## 20. Multi-tenancy and deployment models

### 20.1 Tenancy hierarchy

```text
Organization
  -> Tenant
      -> Business unit
          -> Environment
              -> Cloud account/subscription/project
                  -> Region/cluster
                      -> Resource
```

Every database row, event, evidence object, cache key, workflow, connector request, and tool call must include tenant context.

### 20.2 Isolation

Use:

- Tenant-aware authorization at every API.
- PostgreSQL row-level security where suitable.
- Tenant-scoped encryption and object paths.
- Tenant-scoped workflow IDs.
- Tenant-scoped caches and queues.
- Tenant-scoped model routing and budgets.
- Explicit cross-tenant tests.

### 20.3 Deployment options

#### SaaS control plane plus customer connector runtime

Recommended default:

- Central product control plane.
- Customer-side connector/executor in customer trust zones.
- Outbound mTLS.
- Short-lived local credentials.
- Raw data can remain customer-side; summaries and selected evidence are returned according to policy.

#### Private cloud deployment

- Dedicated control plane per customer or regulated segment.
- Customer-managed network and keys.
- Optional customer-managed models.

#### Fully self-hosted

- Entire stack runs in customer infrastructure.
- Requires a supported installation, upgrade, backup, and observability model.

### 20.4 Cross-account and cross-region

- Use canonical provider resource IDs.
- Support organization-level inventory.
- Use region-aware collectors.
- Record evidence source account and region.
- Handle unavailable regions and eventual consistency.
- Avoid global assumptions about time, endpoints, and identity.

---

## 21. Data architecture

### 21.1 Primary stores

Use PostgreSQL as the primary transactional system of record for the product. Keep SQLite only for local development and lightweight tests behind a repository abstraction.

Recommended supporting stores:

- PostgreSQL for transactional data and projections.
- Object storage for large evidence and audit exports.
- Search index for full-text and semantic retrieval.
- Event broker for ingestion and domain events.
- Redis or equivalent for short-lived caching and rate limits.
- Analytics warehouse for long-term product and operational metrics.

### 21.2 Core relational entities

At minimum:

```text
tenant
organization
business_unit
environment
identity
role
permission
connector
connector_capability
resource
resource_relationship
business_service
service_owner
slo
sla
maintenance_window
change_record
alert
alert_normalization
alert_correlation
incident
incident_alert
incident_workstream
incident_owner
incident_timeline_event
agent_run
agent_event
model_run
tool_call
evidence
hypothesis
hypothesis_evidence
impact_record
knowledge_item
runbook
runbook_version
recovery_plan
recovery_plan_version
action_step
precondition_result
policy_decision
approval_request
approval_decision
action_execution
verification_run
verification_check_result
rollback_execution
feedback
capability
capability_version
capability_certification
audit_event
```

### 21.3 Incident record

Representative fields:

```text
incident_id
 tenant_id
 external_reference
 title
 description
 severity
 state
 sub_status
 incident_class
 primary_resource_id
 primary_service_id
 detected_at
 correlated_at
 acknowledged_at
 diagnosis_ready_at
 resolved_at
 closed_at
 current_owner_id
 commander_id
 current_plan_id
 calibrated_confidence
 customer_impact_status
 sla_deadline
 workflow_id
 workflow_run_id
 created_at
 updated_at
 row_version
```

### 21.4 Evidence storage

Store evidence metadata in PostgreSQL and raw payloads in object storage. Use content hashes to detect duplicates and support integrity checks.

Index evidence by:

- Tenant.
- Incident.
- Resource.
- Source type.
- Observed time.
- Tool call.
- Authority.
- Sensitivity.
- Content hash.

### 21.5 Partitioning and retention

Potential high-volume tables:

- Alerts.
- Timeline events.
- Tool calls.
- Evidence.
- Audit events.
- Model runs.

Partition by time and tenant where required. Define retention separately for:

- Operational incident records.
- Raw telemetry evidence.
- Model input/output metadata.
- Audit records.
- Customer communications.
- Evaluation data.

Legal hold must override normal deletion.

### 21.6 Optimistic concurrency

Use version columns for mutable projections such as incident, plan, and approval status. Reject stale writes rather than silently overwriting concurrent updates.

### 21.7 Event outbox

Use a transactional outbox so business state changes and emitted domain events cannot diverge.

Example:

```text
Transaction:
  update incident state
  insert timeline event
  insert outbox event
Commit

Publisher:
  read unpublished outbox events
  publish to broker
  mark published
```

---

## 22. Event and API architecture

### 22.1 Canonical domain events

Examples:

```text
AlertReceived
AlertNormalized
AlertDeduplicated
AlertCorrelated
IncidentCreated
IncidentUpdated
InvestigationStarted
EvidenceRequested
EvidenceCollected
HypothesisUpdated
DiagnosisReady
PlanDrafted
PlanCompiled
PolicyEvaluated
ApprovalRequested
ApprovalGranted
ActionStarted
ActionCompleted
ActionFailed
VerificationStarted
VerificationCompleted
RollbackStarted
IncidentResolved
IncidentEscalated
FeedbackRecorded
```

Every event should include:

```json
{
  "event_id": "EVT-001",
  "event_type": "EvidenceCollected",
  "event_version": 1,
  "tenant_id": "TEN-001",
  "incident_id": "INC-1234",
  "occurred_at": "2026-08-05T09:48:14Z",
  "correlation_id": "CORR-8821",
  "causation_id": "EVT-000",
  "producer": "capability-gateway",
  "payload": {}
}
```

### 22.2 API groups

#### Incident APIs

```text
GET    /v1/incidents
POST   /v1/incidents
GET    /v1/incidents/{incident_id}
PATCH  /v1/incidents/{incident_id}
POST   /v1/incidents/{incident_id}/assign
POST   /v1/incidents/{incident_id}/escalate
POST   /v1/incidents/{incident_id}/close
GET    /v1/incidents/{incident_id}/timeline
GET    /v1/incidents/{incident_id}/events
```

#### Investigation APIs

```text
POST   /v1/incidents/{incident_id}/investigations
GET    /v1/investigations/{investigation_id}
POST   /v1/investigations/{investigation_id}/questions
POST   /v1/investigations/{investigation_id}/evidence
POST   /v1/investigations/{investigation_id}/hypotheses
PATCH  /v1/hypotheses/{hypothesis_id}
POST   /v1/investigations/{investigation_id}/retry
POST   /v1/investigations/{investigation_id}/cancel
```

#### Plan and approval APIs

```text
POST   /v1/incidents/{incident_id}/plans
GET    /v1/plans/{plan_id}
POST   /v1/plans/{plan_id}/compile
POST   /v1/plans/{plan_id}/validate
POST   /v1/plans/{plan_id}/approval-requests
POST   /v1/approval-requests/{approval_id}/approve
POST   /v1/approval-requests/{approval_id}/reject
POST   /v1/approval-requests/{approval_id}/request-revision
```

#### Execution APIs

```text
POST   /v1/plans/{plan_id}/execute
GET    /v1/executions/{execution_id}
POST   /v1/executions/{execution_id}/cancel
POST   /v1/executions/{execution_id}/rollback
GET    /v1/executions/{execution_id}/verification
```

#### Administration APIs

```text
/v1/admin/connectors
/v1/admin/capabilities
/v1/admin/skill-packs
/v1/admin/policies
/v1/admin/models
/v1/admin/knowledge
/v1/admin/runbooks
/v1/admin/evaluations
/v1/admin/audit-exports
```

### 22.3 API behavior

- Use idempotency keys for create, approve, execute, and rollback operations.
- Use pagination and stable cursors.
- Use standardized error codes.
- Return authorization failures without leaking resource existence.
- Include correlation IDs.
- Use asynchronous job resources for long-running operations.
- Use SSE or WebSocket for live updates.
- Do not block a UI request on an investigation or recovery workflow.

### 22.4 Error contract

```json
{
  "error": {
    "code": "PLAN_PRECONDITION_FAILED",
    "message": "The target execution is no longer in FAILED state.",
    "correlation_id": "CORR-8821",
    "details": {
      "action_id": "ACT-001",
      "precondition": "execution_status == FAILED",
      "observed": "SUCCEEDED"
    },
    "retryable": false
  }
}
```

---

## 23. Connector and extension architecture

### 23.1 Connector runtime

Implement a customer-side connector runtime that:

- Runs inside a customer trust zone.
- Establishes outbound mTLS.
- Registers available capabilities.
- Uses local short-lived credentials.
- Applies local data-loss-prevention rules.
- Executes read and action calls.
- Streams heartbeats and health.
- Buffers safely during temporary disconnection.
- Supports signed upgrades.

### 23.2 Connector SDK

Provide an SDK with:

- Typed capability interface.
- Input/output validation.
- Standard errors.
- Retry and timeout helpers.
- Redaction utilities.
- Evidence-object helpers.
- Audit context.
- Idempotency helper.
- Test harness.
- Permission manifest generator.
- Health endpoint.

### 23.3 Connector contract tests

Every connector must pass:

- Authentication and tenant isolation.
- Permission denial behavior.
- Timeout and retry behavior.
- Rate-limit behavior.
- Data redaction.
- Schema compatibility.
- Idempotency for write tools.
- Audit event generation.
- Failure simulation.
- Version negotiation.

### 23.4 Initial real connectors

Recommended order:

1. AWS CloudWatch logs and metrics.
2. AWS CloudTrail.
3. AWS Config/inventory.
4. AWS Step Functions.
5. AWS Lambda.
6. AWS ECS.
7. AWS SQS/SNS.
8. AWS S3.
9. AWS IAM simulation and Secrets metadata.
10. PostgreSQL/RDS read-only diagnostics.
11. CI/CD/deployment system.
12. ServiceNow or Jira Service Management.
13. Service catalog/CMDB.
14. Knowledge/runbook source.
15. Airflow, Databricks, Glue, or the first customer data platform.

### 23.5 Safe action connectors

Implement action capabilities only after the matching read and verification tools exist.

Example order:

1. Create/update ticket.
2. Send approved communication.
3. Retry an idempotent pipeline.
4. Pause/resume a schedule.
5. Redrive a bounded DLQ batch.
6. Restart a stateless worker.
7. Restore a previous configuration version.
8. Roll back an approved deployment.
9. Restore a schema mapping.
10. Advanced infrastructure actions only after operational evidence and policy mature.

---

## 24. Model architecture and optimization

### 24.1 Provider abstraction

The product must not depend on one model or provider.

```python
from typing import Protocol, TypeVar, Type

T = TypeVar("T")

class ReasoningModelProvider(Protocol):
    async def generate_structured(
        self,
        *,
        task_type: str,
        messages: list[dict],
        response_model: Type[T],
        tenant_id: str,
        data_classification: str,
        timeout_seconds: int,
        budget: dict,
    ) -> T:
        ...
```

Potential providers:

```text
NvidiaNimProvider
OpenAIProvider
AnthropicProvider
AzureOpenAIProvider
LocalModelProvider
CustomerManagedProvider
```

### 24.2 Task-based model routing

| Task | Model requirement |
|---|---|
| Alert normalization | Small, fast, low cost; often deterministic |
| Classification | Small/medium structured model |
| Log and tool-result extraction | Small structured model or deterministic parser |
| Complex RCA | Strong reasoning model |
| Grounding/safety critique | Strong reasoning model, separate invocation |
| Communication drafting | Medium model |
| Summarization and formatting | Small model |

### 24.3 Context strategy

Use progressive disclosure:

1. Canonical incident facts.
2. Compact topology summary.
3. Relevant evidence summaries.
4. On-demand evidence expansion.
5. Raw evidence only when required and permitted.

Never place entire log streams, CMDB exports, or runbook libraries into one prompt.

### 24.4 Context compaction

After each investigation round:

- Preserve evidence IDs.
- Preserve structured facts.
- Preserve hypotheses and changes.
- Summarize low-value conversation.
- Drop redundant raw tool output.
- Maintain a deterministic token budget.

### 24.5 Model budgets

Configure per tenant, severity, and incident class:

- Maximum model calls.
- Maximum tokens.
- Maximum investigation time.
- Maximum tool calls.
- Maximum parallel calls.
- Maximum cost.

When a budget is exhausted, return the best current result and escalate rather than looping indefinitely.

### 24.6 Structured outputs

All model boundaries must use versioned schemas. Validate outputs and retry a limited number of times. Persist validation errors for evaluation.

Do not use Markdown parsing as an application contract.

### 24.7 Prompt and graph versioning

Every model run must identify:

- Prompt template version.
- Graph version.
- Skill-pack version.
- Tool catalog version.
- Response schema version.

Promote changes through offline evaluation, shadow mode, canary, and general availability.

### 24.8 Fallback behavior

If the primary model fails:

- Retry according to provider policy.
- Use a configured fallback model when data policy permits.
- Degrade to deterministic correlation, topology, ownership, and runbook retrieval.
- Surface missing AI capability clearly.
- Never skip approval or policy because a model is unavailable.

---

## 25. Performance, scalability, and cost optimization

### 25.1 Event-driven processing

Use queues and asynchronous workers for:

- Alert ingestion.
- Normalization.
- Correlation.
- Evidence retrieval.
- Model tasks.
- Audit export.
- Knowledge ingestion.
- Evaluation runs.

### 25.2 Backpressure

Implement:

- Per-tenant ingestion quotas.
- Priority queues by severity.
- Connector concurrency limits.
- Model concurrency limits.
- Tool-call budgets.
- Circuit breakers.
- Dead-letter queues.
- Replay.

High-severity incidents may preempt lower-priority background investigations, but must not starve all other tenants.

### 25.3 Caching

Safe cache candidates:

- Service topology.
- Ownership.
- Runbook metadata.
- Static configuration.
- Resource inventory.
- Historical incident embeddings.

Do not trust stale cache for:

- Current execution status.
- Approval state.
- Security policy.
- Action preconditions.
- Verification.

Every cache entry must include tenant, environment, source version, and expiration.

### 25.4 Database optimization

- Index incident state, severity, owner, updated time, tenant, and external reference.
- Index evidence by resource and observed time.
- Partition high-volume event and audit tables.
- Use connection pooling.
- Keep transactions short.
- Use read replicas for analytics if required.
- Archive raw payloads to object storage.
- Use materialized projections for common dashboards.

### 25.5 Cost controls

Track cost per:

- Incident.
- Model run.
- Tool call.
- Connector.
- Tenant.
- Skill pack.

Support budgets and alerts. Use the lowest-cost model that meets evaluated quality. Deduplicate evidence retrieval and reuse immutable evidence safely.

---

## 26. Observability and operation of NemoGuard itself

NemoGuard is an operational platform and must be supportable.

### 26.1 Trace context

Propagate:

```text
tenant_id
incident_id
workflow_id
workflow_run_id
investigation_id
agent_run_id
model_run_id
tool_call_id
correlation_id
request_id
```

Instrument:

- API requests.
- Temporal workflows and activities.
- LangGraph nodes.
- Model calls.
- Tool calls.
- Policy decisions.
- Connector calls.
- Database operations.
- Event publishing.
- Approval latency.
- Execution and verification.

### 26.2 Product SLOs

Define and measure, for example:

- Alert ingestion availability.
- Time from alert receipt to incident creation.
- Investigation-start latency.
- Event-stream freshness.
- Approval durability.
- Action exactly-once safety.
- Audit-event completeness.
- Connector health.
- UI availability.

Suggested starting targets must be calibrated, but include strict invariants:

```text
0 cross-tenant data leakage
0 unapproved production mutations
100% write actions audited
100% executed plans have verification policy
100% approval checks bind to current plan hash
```

### 26.3 Operational dashboards

Monitor:

- Ingestion rate and lag.
- Correlation queue depth.
- Temporal task queue health.
- LangGraph failures.
- Model latency, errors, and cost.
- Tool-call latency and failure.
- Connector heartbeat.
- Policy denials.
- Approval latency.
- Action and verification failure.
- Audit pipeline lag.
- Database and event-broker health.

### 26.4 Self-protection

If NemoGuard is degraded:

- Disable autonomous writes.
- Preserve read-only incident visibility.
- Queue new alerts safely.
- Surface platform status.
- Keep audit recording available.
- Fail closed for authorization and approval.

---

## 27. Testing and evaluation strategy

A system that operates production environments cannot be validated through demonstrations alone.

### 27.1 Test layers

#### Unit tests

Cover:

- Normalization.
- Correlation scoring.
- State transitions.
- Typed schemas.
- Policy decisions.
- Plan compilation.
- Plan hashing.
- Idempotency.
- Graph traversal.
- Verification assertions.
- Redaction.

#### Connector contract tests

Run against emulators, sandboxes, and real nonproduction systems.

#### Integration tests

Cover:

- Alert to incident.
- Incident to investigation.
- Evidence retrieval.
- Model structured output.
- Plan compilation.
- Approval.
- Action execution.
- Verification.
- Rollback.
- Audit completeness.

#### End-to-end tests

Exercise the real API, Temporal workflow, LangGraph investigation, gateway, connector, database, event stream, and UI projection.

#### Replay tests

Replay sanitized historical incidents and compare NemoGuard with confirmed outcomes.

#### Performance tests

Measure:

- Alert bursts.
- Concurrent investigations.
- Large topology traversals.
- Tool-call fan-out.
- Evidence storage.
- Event stream load.
- Approval and execution concurrency.

#### Security tests

Cover:

- Cross-tenant access.
- Prompt injection.
- Malicious evidence.
- Tool argument injection.
- Approval replay.
- Plan tampering.
- SSRF.
- Secret leakage.
- Privilege escalation.
- Denial of wallet.

#### Chaos and resilience tests

Inject:

- Model provider failure.
- Connector timeout.
- Event broker outage.
- Temporal worker restart.
- Database failover.
- Partial action success.
- Verification timeout.
- Regional unavailability.
- Duplicate events.
- Out-of-order events.

### 27.2 Support-engineering benchmark

Build an evaluation corpus from:

- Sanitized historical incidents.
- Synthetic incidents.
- Chaos experiments.
- Known error injection.
- Multi-fault scenarios.
- Ambiguous incidents.
- False alerts.
- Misleading evidence.
- Missing evidence.
- Incidents requiring escalation.
- Unsafe remediation requests.

Each scenario should define:

```yaml
scenario_id: ECS-OOM-DEPLOY-001
incident_class: ECS_OOM_LOOP
environment: test
signals: []
ground_truth:
  primary_cause: TASK_MEMORY_REDUCTION
  contributing_factors: []
expected_evidence:
  mandatory:
    - stopped_task_reason
    - task_definition_diff
    - deployment_timestamp
acceptable_hypotheses: []
unacceptable_claims: []
expected_impact: {}
allowed_actions:
  - ROLLBACK_DEPLOYMENT
unsafe_actions:
  - INCREASE_MEMORY_WITHOUT_CHANGE_REVIEW
verification_policy: VP-ECS-RECOVERY-003
requires_escalation: false
```

### 27.3 Metrics

#### Detection and correlation

- Deduplication precision and recall.
- Correlation precision and recall.
- Incorrect merge rate.
- Incorrect split rate.
- Time to incident creation.

#### Diagnosis

- Root-cause top-1 accuracy.
- Root-cause top-3 accuracy.
- Evidence precision.
- Evidence coverage.
- Unsupported-claim rate.
- Contradiction detection.
- Time to first useful hypothesis.
- Correct escalation rate.
- Confidence calibration error.

#### Impact

- Dependency recall.
- Business-impact accuracy.
- Owner identification accuracy.
- SLA-breach prediction accuracy.

#### Tool use

- Correct tool-selection rate.
- Unnecessary call rate.
- Permission-denial handling.
- Failed-call recovery.
- Cross-account target accuracy.
- Cost per investigation.

#### Remediation

- Plan executability.
- Action success rate.
- Idempotency violations.
- Verification accuracy.
- Rollback success.
- Unsafe-action block rate.
- Unapproved-write rate.

#### Human value

- Recommendation acceptance.
- Engineer correction rate.
- Mean time to acknowledge reduction.
- Mean time to diagnose reduction.
- Mean time to recovery reduction.
- Number of systems manually consulted.
- User trust score.
- Shift-handover quality.

### 27.4 Minimum release gates

Calibrate values by incident class, but enforce these invariants:

```text
100% of write actions pass through the policy gateway
100% of write actions have an audit record
0 unapproved production mutations
0 cross-tenant evidence leakage
100% of executed plans have verification policies
100% of approvals bind to the current plan hash
100% of reversible actions declare rollback/compensation
No capability reaches autonomous production without certification
```

Recommended quality targets for a supported incident class before supervised production:

```text
RCA top-1 accuracy >= 85%
RCA top-3 accuracy >= 95%
Material-claim evidence coverage >= 95%
Unsafe-action block rate = 100% in the evaluation suite
Plan executability >= 95%
Verification false-positive rate < 1%
Correct escalation rate >= 95%
```

These are starting targets and must be adjusted using real pilot data.

---

## 28. Rollout and autonomy progression

Never jump from LocalStack directly to autonomous production.

### 28.1 Progression stages

```text
Offline evaluation
    -> historical replay
    -> read-only shadow mode
    -> recommendation mode
    -> approved nonproduction execution
    -> approved production execution
    -> bounded autonomous execution
```

### 28.2 Shadow mode

In shadow mode:

- NemoGuard observes real incidents.
- It performs investigation and drafts plans.
- It does not act.
- Engineers record actual diagnosis and action.
- Results are compared offline.
- Gaps become evaluation scenarios.

### 28.3 Recommendation mode

Operators can use NemoGuard's evidence and plan, but execution remains external. Measure acceptance and correction.

### 28.4 Supervised execution

Enable a small set of reversible actions with approval, verification, and rollback.

### 28.5 Bounded autonomy

Enable only when:

- The incident signature is stable.
- The diagnosis is strongly evidenced.
- The capability is certified.
- The action is reversible and idempotent.
- Blast radius is bounded.
- Verification is reliable.
- Historical success is sufficient.
- Tenant policy explicitly permits it.

Autonomy must immediately suspend if drift, verification failures, policy changes, or connector health problems exceed thresholds.

---

## 29. Product roadmap

### Phase 0 - Baseline and safety freeze

**Objective:** Create a trustworthy baseline before adding more agents or tools.

Deliverables:

- Freeze current schemas and record baseline architecture.
- Add end-to-end test coverage for the existing lab scenario.
- Remove hardcoded success statuses from tests unless explicitly marked simulation.
- Add feature flags separating simulation, LocalStack, nonproduction real, and production modes.
- Add a product-wide correlation ID.
- Add OpenTelemetry instrumentation.
- Add structured error codes.
- Create the capability and incident-class registry.
- Establish security threat model and data classification.

Exit criteria:

- Existing POC behavior is reproducible.
- Simulated behavior is visibly labeled and cannot be confused with real execution.
- Every model and tool call is observable.

### Phase 1 - Generic capability gateway and execution engine

**Objective:** Remove the largest current limitation: free-text plans and hardcoded action paths.

Deliverables:

- Versioned capability registry.
- Typed read and action contracts.
- Abstract action-intent schema.
- Deterministic Plan Compiler.
- Canonical plan and hash.
- Policy decision interface.
- Approval binding.
- Generic Temporal execution workflow.
- Idempotency and target locks.
- Action-level audit.
- Verification-policy engine.
- Rollback/compensation workflow.
- Remove hardcoded passing verification.

First certified actions:

- Create/update ITSM ticket.
- Retry an idempotent job.
- Pause/resume a schedule.
- Redrive a bounded DLQ batch.

Exit criteria:

- An approved typed plan invokes a registered connector capability.
- Execution modifies a real nonproduction target.
- Independent verification determines success.
- A failed verification triggers rollback or escalation.

### Phase 2 - Real evidence fabric and change intelligence

**Objective:** Make diagnosis comparable to an experienced engineer.

Deliverables:

- Canonical evidence model.
- Raw evidence object storage.
- Redaction pipeline.
- CloudWatch logs/metrics connector.
- CloudTrail connector.
- AWS Config/inventory connector.
- Deployment/CI connector.
- Evidence authority and freshness model.
- Evidence bundles.
- Tool-call and evidence audit.
- Change-to-incident correlation.

Exit criteria:

- RCA uses multiple independent source types.
- Every material claim cites evidence.
- Recent changes are evaluated automatically.

### Phase 3 - Hypothesis-driven LangGraph investigation

**Objective:** Replace linear agent calls with an evidence-seeking investigation.

Deliverables:

- Hypothesis ledger.
- Initial hypothesis generation.
- Evidence-request planner.
- Information-gain-based tool selection.
- Supporting and contradicting evidence.
- Stop and escalation conditions.
- Independent critic with tool access.
- Calibrated confidence.
- Investigation budgets.
- Human clarification interrupts.

Exit criteria:

- The agent can distinguish at least three competing causes in benchmark incidents.
- It requests more evidence when needed instead of producing a confident unsupported answer.

### Phase 4 - Real service, ownership, and business graph

**Objective:** Support multi-application and business-impact reasoning.

Deliverables:

- Canonical resource model.
- Typed relationships.
- CMDB/service-catalog connector.
- Cloud resource inventory.
- Business-service and data-lineage mapping.
- Ownership and on-call integration.
- SLO/SLA integration.
- Technical and business blast-radius queries.
- Graph visualization and API.

Exit criteria:

- Incident impact is computed across multiple applications and business services.
- Owners and escalation routes are authoritative.

### Phase 5 - Domain skill packs

**Objective:** Build deep, certifiable competencies.

Initial packs:

1. AWS serverless and Step Functions.
2. Data pipeline and integration.
3. ECS/container runtime.
4. SQS/SNS messaging.
5. RDS/PostgreSQL.
6. Network and IAM diagnostics.

Each pack must ship with:

- Manifest.
- Tool contracts.
- Permissions.
- Decision trees.
- Runbooks.
- Actions.
- Verification.
- Rollback.
- Evaluation suite.
- Certification record.

### Phase 6 - Production user and administration experience

**Objective:** Make the platform usable by real operations teams.

Deliverables:

- Replace or augment Streamlit with a production web application when backend flows are stable.
- Operator workbench.
- Major incident mode.
- Approval inbox.
- Evidence explorer.
- Timeline and agent activity.
- Administration console.
- Connector health.
- Policy management.
- Capability catalog.
- Runbook governance.
- Audit explorer.
- ChatOps and ITSM integration.
- Accessibility and responsive design.

### Phase 7 - Enterprise hardening

**Objective:** Support secure multi-tenant deployments.

Deliverables:

- PostgreSQL production migration.
- OIDC/SAML and SCIM.
- RBAC/ABAC.
- Tenant isolation and row-level security.
- Customer-side connector runtime.
- mTLS and short-lived credentials.
- Data residency.
- Retention and legal hold.
- Audit export and tamper evidence.
- Disaster recovery.
- Regional deployment.
- SLOs and operational runbooks.
- Supply-chain security and signed artifacts.

### Phase 8 - Supervised production remediation

**Objective:** Operate selected capabilities in real production with human approval.

Deliverables:

- Customer pilot environments.
- Change-control integration.
- Production approval policies.
- On-call escalation.
- Safety monitoring.
- Outcome review.
- Capability-by-capability production certification.

### Phase 9 - Bounded autonomy

**Objective:** Automatically resolve selected low-risk incident classes.

Deliverables:

- Autonomy policy.
- Automatic suspension criteria.
- Drift monitoring.
- High-confidence certification.
- Operator override.
- Autonomous-action reporting.

---

## 30. Detailed first 90-day implementation plan

### Days 1-15: Baseline and contracts

- Inventory current LangGraph nodes, Temporal workflows, tools, database tables, prompts, and model providers.
- Add integration tests for current incident flow.
- Mark every simulated path explicitly.
- Define canonical resource, evidence, hypothesis, action-intent, compiled-action, policy-decision, approval, execution, and verification models.
- Introduce capability IDs and versions.
- Introduce tenant/environment/account/region context to all tool calls.
- Add standardized errors and correlation IDs.

### Days 16-30: Capability gateway

- Implement the registry service.
- Wrap all existing tools through the gateway.
- Add input/output schema validation.
- Add authorization context.
- Add audit events.
- Add rate limits and timeouts.
- Store tool results as evidence.
- Remove direct tool imports from agents.

### Days 31-45: Plan compiler and approvals

- Replace free-text `tool_name` plan fields with abstract intents.
- Implement capability resolution.
- Implement plan compilation.
- Add canonical JSON serialization and plan hashing.
- Add policy decision adapter.
- Add approval requests bound to the hash.
- Invalidate approval on plan changes.

### Days 46-60: Execution and verification

- Implement generic Temporal action activities.
- Add idempotency keys and target locks.
- Implement dry-run support.
- Implement real nonproduction retry and pause/resume actions.
- Implement verification policy execution.
- Remove hardcoded pass behavior.
- Implement rollback or escalation.

### Days 61-75: Evidence and hypothesis loop

- Add evidence model and object storage.
- Add CloudWatch and CloudTrail connectors.
- Add evidence authority and redaction.
- Implement hypothesis ledger.
- Update LangGraph to request evidence iteratively.
- Give the critic independent evidence tools.

### Days 76-90: Evaluation and pilot preparation

- Build 30-50 benchmark scenarios across the first incident classes.
- Add evaluation dashboards.
- Add shadow-mode configuration.
- Add operator correction and feedback.
- Add first real service-catalog/ownership integration.
- Complete threat-model review.
- Prepare one nonproduction pilot.

---

## 31. Prioritized engineering backlog

### P0 - Required before claiming real execution

1. Generic capability registry.
2. Typed action-intent schema.
3. Deterministic Plan Compiler.
4. Generic action execution engine.
5. Plan hashing and approval integrity.
6. Independent verification engine.
7. Remove hardcoded recovery success.
8. Idempotency and concurrency locks.
9. Action and verification audit events.
10. Feature flags that separate simulation from real execution.
11. End-to-end execution test.
12. Policy enforcement outside prompts.

### P1 - Required before real-world diagnosis

1. Canonical evidence fabric.
2. CloudWatch logs and metrics.
3. CloudTrail and deployment/change history.
4. Real service/resource inventory.
5. Hypothesis ledger.
6. Contradiction tracking.
7. Independent critic with tools.
8. Real CMDB/service ownership.
9. Multi-account and multi-region context.
10. Network and IAM diagnostic tools.
11. Warehouse and data-platform read tools.
12. Calibrated confidence.

### P2 - Required for enterprise pilot

1. PostgreSQL production migration.
2. SSO and SCIM.
3. Tenant isolation.
4. Customer-side connector runtime.
5. Operator and approval UX.
6. Administration console.
7. Runbook governance.
8. Audit explorer and export.
9. OpenTelemetry and SLOs.
10. Security and adversarial testing.
11. Shadow-mode comparison.
12. Support and onboarding documentation.

### P3 - Expansion and autonomy

1. Additional domain skill packs.
2. Major incident coordination.
3. ChatOps.
4. Customer communication workflows.
5. Past-incident case memory.
6. Automated postmortem draft.
7. Bounded autonomy.
8. Multi-cloud and on-prem connectors.

---

## 32. Recommended repository structure

Adapt this to the current repository rather than performing a disruptive rewrite.

```text
src/
  api/
    main.py
    dependencies.py
    middleware/
      auth.py
      tenancy.py
      correlation.py
    routes/
      incidents.py
      investigations.py
      evidence.py
      plans.py
      approvals.py
      executions.py
      admin_connectors.py
      admin_capabilities.py
      admin_policies.py
      admin_models.py
      audit.py
  domain/
    models/
      incident.py
      evidence.py
      hypothesis.py
      impact.py
      plan.py
      approval.py
      execution.py
      verification.py
      capability.py
      audit.py
    services/
      incident_service.py
      correlation_service.py
      graph_service.py
      impact_service.py
      plan_compiler.py
      confidence_calibrator.py
    events.py
    errors.py
  workflows/
    temporal/
      incident_workflow.py
      action_workflow.py
      verification_workflow.py
      rollback_workflow.py
      activities/
    langgraph/
      investigation_graph.py
      state.py
      nodes/
        supervisor.py
        watcher.py
        rca.py
        impact.py
        runbook.py
        critic.py
        communication.py
      routing.py
      prompts/
  capabilities/
    registry.py
    gateway.py
    policy.py
    authorization.py
    idempotency.py
    locks.py
    evidence_adapter.py
    manifests/
    providers/
      aws/
      data/
      itsm/
      knowledge/
  connectors/
    sdk/
    runtime/
    aws/
      cloudwatch.py
      cloudtrail.py
      config.py
      lambda.py
      ecs.py
      stepfunctions.py
      sqs.py
      s3.py
      iam.py
      rds.py
      network.py
    data/
    itsm/
    cmdb/
    knowledge/
  policies/
    engine.py
    bundles/
  evidence/
    service.py
    redaction.py
    authority.py
    storage.py
    bundles.py
  knowledge/
    ingestion.py
    retrieval.py
    governance.py
  audit/
    writer.py
    integrity.py
    export.py
  store/
    repositories/
    migrations/
    outbox.py
  observability/
    tracing.py
    metrics.py
    logging.py
  evaluation/
    runner.py
    metrics.py
    datasets/
  ui/
    # current Streamlit UI can remain temporarily
connector_runtime/
web/
  # future production React/Next.js application
skills/
  aws_ecs/
  aws_serverless/
  data_pipeline/
  database/
  network/
  identity/
tests/
  unit/
  contract/
  integration/
  e2e/
  replay/
  security/
  chaos/
```

---

## 33. Representative Pydantic models

These are directional contracts. The coding agent should align names with the current codebase and create migrations carefully.

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field


class Authority(str, Enum):
    AUTHORITATIVE = "AUTHORITATIVE"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EvidenceRecord(BaseModel):
    evidence_id: str
    tenant_id: str
    incident_id: str
    source_type: str
    source_system: str
    resource_ids: list[str] = Field(default_factory=list)
    observed_at: datetime
    retrieved_at: datetime
    summary: str
    structured_facts: dict[str, Any] = Field(default_factory=dict)
    raw_object_uri: str | None = None
    content_hash: str
    authority: Authority
    sensitivity: str
    redaction_status: str
    tool_call_id: str


class HypothesisStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    PROBABLE = "PROBABLE"
    UNLIKELY = "UNLIKELY"
    REJECTED = "REJECTED"
    CONFIRMED = "CONFIRMED"


class Hypothesis(BaseModel):
    hypothesis_id: str
    incident_id: str
    statement: str
    cause_category: str
    status: HypothesisStatus
    raw_model_confidence: float = Field(ge=0, le=1)
    calibrated_confidence: float = Field(ge=0, le=1)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    missing_evidence_requests: list[str] = Field(default_factory=list)


class ActionIntent(BaseModel):
    intent_type: str
    target_resource_type: str
    target_resource_id: str
    reason: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    expected_effect: str


class RiskLevel(str, Enum):
    READ_ONLY = "READ_ONLY"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    PROHIBITED = "PROHIBITED"


class CompiledAction(BaseModel):
    action_id: str
    sequence: int
    capability_id: str
    capability_version: str
    tenant_id: str
    environment: str
    account_id: str | None = None
    region: str | None = None
    resource_id: str
    arguments: dict[str, Any]
    risk_level: RiskLevel
    precondition_policy_id: str | None = None
    approval_policy_id: str
    idempotency_key: str
    verification_policy_id: str
    rollback_policy_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class RecoveryPlan(BaseModel):
    plan_id: str
    version: int
    incident_id: str
    summary: str
    actions: list[CompiledAction]
    plan_hash: str
    created_at: datetime
    status: Literal[
        "DRAFT",
        "COMPILED",
        "VALIDATED",
        "AWAITING_APPROVAL",
        "APPROVED",
        "EXECUTING",
        "COMPLETED",
        "INVALIDATED",
        "FAILED",
    ]
```

---

## 34. LangGraph investigation design

### 34.1 Graph state

```python
class InvestigationState(TypedDict):
    tenant_id: str
    incident_id: str
    investigation_id: str
    incident_class: str | None
    resource_context: dict
    alert_ids: list[str]
    signal_summary: dict
    selected_skill_packs: list[str]
    hypotheses: list[dict]
    evidence_ids: list[str]
    requested_evidence: list[dict]
    technical_impact: dict
    business_impact: dict
    runbook_matches: list[dict]
    unknowns: list[str]
    investigation_round: int
    remaining_tool_budget: int
    remaining_model_budget: int
    critic_result: dict | None
    action_intents: list[dict]
    escalation: dict | None
    errors: list[dict]
```

### 34.2 Graph nodes

```text
load_incident_context
normalize_signal_context
select_skill_packs
generate_initial_hypotheses
plan_evidence_requests
execute_read_capabilities
update_hypotheses
run_parallel_domain_analysis
calculate_impact
retrieve_knowledge
aggregate_findings
grounding_critic
request_more_evidence
request_human_clarification
generate_action_intents
finalize_diagnosis
escalate
```

### 34.3 Conditional routing

```text
If mandatory context missing -> request_human_clarification
If evidence request budget remains -> execute_read_capabilities
If critic returns MORE_EVIDENCE_REQUIRED -> plan_evidence_requests
If critic returns PLAN_UNSAFE -> generate_action_intents or escalate
If confidence insufficient and budget exhausted -> escalate
If diagnosis sufficient -> generate_action_intents
```

### 34.4 Investigation boundaries

LangGraph must not:

- Execute production mutations.
- Override policy.
- Mark recovery verified.
- Directly update approval state.
- Bypass the capability gateway.

It returns a structured diagnosis and abstract action intents to the Temporal-controlled operational workflow.

---

## 35. Temporal workflow design

### 35.1 Incident workflow

```text
Receive/attach normalized alerts
    -> create or update incident projection
    -> start investigation activity
    -> wait for investigation result
    -> compile plan
    -> evaluate policy
    -> request approval or auto-authorize certified action
    -> wait for approval signal with timeout
    -> execute actions sequentially or in approved parallel groups
    -> verify each action and overall recovery
    -> rollback/compensate on failure when required
    -> resolve or escalate
    -> schedule post-incident review
```

### 35.2 Workflow signals

```text
AddAlert
AddHumanEvidence
CorrectHypothesis
RequestAdditionalInvestigation
ApprovePlan
RejectPlan
RequestPlanRevision
CancelExecution
TriggerRollback
EscalateIncident
```

### 35.3 Workflow queries

```text
GetCurrentState
GetPendingApproval
GetExecutionProgress
GetVerificationProgress
GetOutstandingHumanTasks
```

### 35.4 Temporal requirements

- Workflow code must be deterministic.
- External calls occur in activities.
- Use retry policies appropriate to each connector/action.
- Use workflow versioning for deployed changes.
- Use stable workflow IDs scoped by tenant and incident.
- Support cancellation and compensation.
- Never depend on UI session state.

---

## 36. Golden-path incident competency

Implement one real, production-quality competency before expanding broadly.

### Recommended first competency: deployment-driven data-pipeline schema regression

#### Detection

- Ingestion failure alert.
- Downstream blocked alerts.
- Data freshness alert.
- Recent deployment event.

#### Correlation

- Merge downstream symptoms with the upstream failure using topology, time, and change context.
- Exclude unrelated concurrent alerts.

#### Evidence

- Application logs showing missing column.
- Schema history.
- Deployment/configuration diff.
- Source file metadata and row count.
- Downstream dependency graph.
- Business data-product mapping.

#### Hypotheses

1. Deployment introduced incompatible schema mapping.
2. Source file omitted the expected column.
3. Database/connectivity failure produced an incomplete load.

#### Diagnosis

The first hypothesis becomes probable only when the deployment diff and schema history support it and source-file integrity contradicts hypothesis 2.

#### Plan intent

```text
RESTORE_PREVIOUS_SCHEMA_MAPPING
VALIDATE_REQUIRED_COLUMNS
RETRY_IDEMPOTENT_INGESTION
VERIFY_ROW_COUNTS
RESUME_DOWNSTREAM_PIPELINE
VERIFY_DATA_PRODUCT_FRESHNESS
```

#### Approval

Require production operator approval because a configuration version changes.

#### Execution

- Restore the previous approved mapping version.
- Validate schema.
- Create a new retry execution with an idempotency key.
- Resume downstream jobs only after upstream success.

#### Verification

- Required columns present.
- Expected row count and checksum within tolerance.
- Upstream run succeeded.
- Downstream blocked count is zero.
- Data products meet freshness threshold.
- No new critical alerts during the observation window.

#### Rollback

Restore the newer mapping if the recovery plan itself causes a new regression, then escalate to the application/data owner.

### Golden-path end-to-end test

```text
POST alert batch
-> wait for one correlated incident
-> wait for DIAGNOSIS_READY
-> assert evidence and hypotheses exist
-> assert compiled plan has registered capabilities
-> approve plan
-> execute plan
-> wait for verification
-> assert incident RESOLVED
-> assert all write actions audited
-> assert all material claims cite evidence
-> assert no hardcoded success rows were inserted
```

---

## 37. Coding-agent implementation rules

The coding agent receiving this document must follow these rules.

### 37.1 Preserve working foundations

Do not rewrite LangGraph, Temporal, FastAPI, Pydantic models, and the existing database wholesale. First map current code to the target architecture, then replace weak boundaries incrementally.

### 37.2 Work in vertical slices

A vertical slice must include:

- Domain model.
- Migration.
- API.
- Workflow.
- Capability or connector.
- Policy.
- Audit.
- Tests.
- UI projection where relevant.

Do not implement dozens of disconnected tool stubs.

### 37.3 Tests before behavior claims

For every new capability, add:

- Unit tests.
- Contract tests.
- Integration tests.
- Failure tests.
- Policy tests.
- Audit assertions.
- Verification tests.

### 37.4 No hidden simulation

All simulated connectors and actions must be named and labeled as simulation. Production code paths must fail closed when a real connector is unavailable. Never silently substitute a mock success.

### 37.5 No free-text execution

The agent may not emit arbitrary Python names, shell commands, SQL, URLs, or SDK method names for execution. It emits a known action intent. The deterministic compiler resolves the intent to a registered capability.

### 37.6 No policy in prompts only

Prompt guidance may improve behavior, but every safety-critical rule must have code or policy-engine enforcement.

### 37.7 No self-verification

An action capability cannot declare the incident resolved. Only the verification engine can do so after checking independent postconditions.

### 37.8 Migrations and compatibility

- Use versioned database migrations.
- Provide backward-compatible API changes where practical.
- Version events, tool contracts, prompts, and capability manifests.
- Do not mutate historical plans or audit records.

### 37.9 Observability

Every new workflow, node, tool, connector, policy decision, and model call must be instrumented with correlation context.

### 37.10 Definition before implementation

Before writing a new action tool, define:

```text
Incident class
Diagnostic evidence
Action intent
Capability contract
Permissions
Risk
Preconditions
Approval
Idempotency
Verification
Rollback
Evaluation scenario
Owner
```

If any field is missing, the capability is not ready to implement.

---

## 38. Definition of done

NemoGuard is ready for a controlled enterprise pilot only when all of the following are true.

### Product and workflow

- Alerts are ingested asynchronously.
- Related alerts correlate into one incident using deterministic and topology-aware logic.
- The workflow survives restarts.
- Investigation is hypothesis-driven.
- Evidence comes from multiple authoritative sources.
- Alternative hypotheses and contradictions are visible.
- Technical and business impact are computed.
- Recovery plans are typed and executable.
- Approvals bind to the exact plan hash.
- Actions execute through the gateway.
- Verification is independent.
- Rollback or escalation works.

### Safety

- No arbitrary shell or unrestricted SQL is available.
- All writes pass policy.
- All writes are authorized and audited.
- Secrets never reach model context.
- Cross-tenant access tests pass.
- Prompt-injection tests pass.
- The platform fails closed for approval and authorization.

### Operations

- PostgreSQL is the production source of truth.
- OpenTelemetry traces connect alert, investigation, tool, approval, execution, and verification.
- SLOs and runbooks exist for NemoGuard itself.
- Backups and disaster recovery are tested.
- Connector health and permission drift are monitored.

### User experience

- Operators can understand current state, evidence, unknowns, impact, and plan.
- Approvers see exact actions and risk.
- Administrators can govern connectors, policies, capabilities, models, and knowledge.
- Auditors can reconstruct every decision and action.
- Major incidents support workstreams, decisions, communications, and handover.

### Quality

- Supported incident classes meet release metrics.
- Every capability has an evaluation suite.
- Shadow-mode results have been reviewed by real support engineers.
- Human corrections are captured.
- Autonomous execution is disabled unless explicitly certified.

---

## 39. Immediate next actions for the current codebase

Execute these in order:

1. Create a branch dedicated to the generic capability gateway.
2. Inventory every existing read and write tool and assign a canonical capability ID.
3. Wrap all existing tools behind one gateway interface.
4. Introduce tenant, environment, account, region, incident, and actor context into every call.
5. Replace free-text executable plan steps with `ActionIntent` objects.
6. Implement the deterministic Plan Compiler.
7. Create canonical plan serialization and plan hashing.
8. Bind approvals to the hash.
9. Implement one generic Temporal action activity that resolves a capability from the registry.
10. Implement idempotency, locks, retries, and structured errors.
11. Replace hardcoded verification with a real verification policy for the first incident class.
12. Implement rollback/escalation for failed verification.
13. Create the canonical evidence record and store all tool outputs through it.
14. Add CloudTrail/change history to the investigation.
15. Implement the hypothesis ledger and evidence-seeking loop.
16. Give the Grounding Critic independent read access through the gateway.
17. Add a real service/ownership source for one pilot environment.
18. Build the first competency evaluation suite.
19. Run in shadow mode against real nonproduction incidents.
20. Review results with experienced support engineers before enabling production actions.

---

## 40. Final architectural position

The target platform should use:

- **LangGraph** for bounded, evidence-driven investigation.
- **Temporal** for durable incident lifecycle, approval, execution, verification, and rollback.
- **FastAPI** for product APIs and integration boundaries.
- **PostgreSQL** for transactional state and queryable projections.
- **A governed capability gateway** as the only access path to operational tools.
- **Customer-side connector runtimes** for secure access to customer trust zones.
- **A policy-as-code layer** for risk, authorization, and approvals.
- **Object storage and an evidence fabric** for traceable source material.
- **OpenTelemetry** for end-to-end observability.
- **Domain skill packs** as the unit of support competence and certification.

The most important product principle is:

> NemoGuard becomes comparable to a strong support engineer not by giving a general agent hundreds of tools, but by certifying complete operational competencies one incident class, one domain, and one safe action at a time.

The first engineering priority is the generic action engine, independent verification, real change intelligence, and multi-source evidence. Adding more LLM agents before these foundations exist will increase apparent sophistication without producing dependable operational competence.
