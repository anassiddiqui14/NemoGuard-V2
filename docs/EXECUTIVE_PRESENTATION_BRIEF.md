# NemoGuard Pipeline Copilot — Executive & Technical Brief

*Prepared for leadership presentation. Reflects the actual, current codebase (not aspirational).*

---

## 1. What it is, in one paragraph

NemoGuard is an **autonomous AI Incident Commander for data pipelines**. When a
data pipeline job fails (schema drift, OOM crash, partial writes, poison-pill
messages, database outages, etc.), NemoGuard automatically: detects the
alert → correlates it to a new or existing incident → runs a real multi-agent
AI investigation to find the root cause → proposes a governed recovery plan →
requires a human to approve any risky action → executes the approved plan
through a safe, sandboxed capability layer → **independently verifies** the
fix actually worked → and only then marks the incident resolved. Every step
is logged to an immutable audit trail.

It is built to replace (or dramatically accelerate) the first 30–60 minutes
of a data-platform on-call engineer's job: triage, root-cause, and drafting
a remediation plan.

---

## 2. The core value proposition

| Traditional on-call | NemoGuard |
|---|---|
| Engineer pages in, manually greps logs, checks CloudWatch, guesses root cause | AI agents pull real logs/metrics/S3/CloudWatch evidence automatically, in seconds-to-minutes |
| Root cause written in a Slack thread, knowledge lost after the incident | Root cause + evidence + full reasoning trail persisted, auditable, and re-used for future similar incidents ("Incident Memory") |
| Remediation is manual, ad-hoc, no verification that it actually worked | Remediation is a governed, versioned plan; execution goes through a safety gateway; resolution requires **independent, automated verification** — never self-reported |
| No safety net against an AI taking a wrong/risky action | Every medium/high-risk action requires explicit human approval; a "Grounding Critic" agent independently re-verifies claims before any plan reaches a human |

---

## 3. High-level architecture

```
 ┌──────────────┐      Webhook       ┌─────────────────────────────┐
 │  Monitoring   │ ─────────────────▶│   Watcher Agent (LLM)        │
 │ (CloudWatch,  │                    │  classify noise vs signal   │
 │  Datadog, ...) │                    └───────────┬─────────────────┘
 └──────────────┘                                   │
                                    Deterministic    │ correlate to new
                                    Correlator Engine│ or existing incident
                                    (run_id/topology)│
                                                      ▼
                                          ┌───────────────────────┐
                                          │      INCIDENT          │
                                          │  (Postgres, versioned) │
                                          └───────────┬────────────┘
                                                       │ Temporal workflow
                                                       ▼
                            ┌──────────────────────────────────────────┐
                            │      Multi-Agent Investigation           │
                            │        (LangGraph state machine)         │
                            │                                          │
                            │   RCA Agent ──▶ Impact Agent  ─┐          │
                            │       │                        ├─▶ Grounding │
                            │       └──▶ Runbook Agent ───────┘   Critic  │
                            │                                          │
                            └──────────────────┬───────────────────────┘
                                                ▼
                                   Recovery Plan (steps + risk level)
                                                │
                                     Human approval required
                                     for MEDIUM/HIGH risk steps
                                                ▼
                            ┌──────────────────────────────────────────┐
                            │   Governed Capability Gateway            │
                            │  precondition check → execute →          │
                            │  INDEPENDENT verification                │
                            └──────────────────┬───────────────────────┘
                                                ▼
                                    RESOLVED (only if verified)
                                     or FAILED / ESCALATED
```

---

## 4. Where the AI agents actually live

All agents are Python classes under **`src/domain/agents/`**, each backed by
a real NVIDIA Nemotron LLM call (not a mock/simulation):

| Agent | File | Model | Role |
|---|---|---|---|
| **Watcher Agent** | `watcher_agent.py` | Nemotron Super 120B | First-line triage: is this webhook real signal or noise? Normalizes arbitrary payload shapes into NemoGuard's canonical alert schema. Detects "recovered" signals from external monitors. |
| **RCA Agent** | `rca_agent.py` | Nemotron Ultra 550B | Root Cause Analysis. Has **tool-calling access** to real logs, CloudWatch, S3, Lambda metrics, RDS/ECS status, IAM checks, recent-change history. Produces a ranked **hypothesis ledger** (multiple competing root-cause theories with supporting/contradicting evidence), not just one guess. |
| **Dependency (Impact) Agent** | `dependency_agent.py` | — | Blast-radius analysis: which downstream data products/jobs are BLOCKED or AT_RISK, using the real CMDB topology. |
| **Runbook Agent** | `runbook_agent.py` | — | Matches the confirmed root cause against a real runbook library and proposes concrete remediation steps. |
| **Grounding Critic** | `langgraph_investigator.py` (`GroundingCritic` class) | Nemotron Ultra 550B | **The final safety gate.** Read-only tool access only (cannot take actions). Independently re-verifies RCA/Impact/Runbook's factual claims before a plan is allowed to reach a human. Enforces hard policy rules in code (e.g. "never rerun a write job without checking for a partial write first") — this check happens in Python, not just via prompting, so the LLM cannot talk its way around it. |
| **Commander Live Agent** | `commander_live_agent.py` | — | Conversational assistant ("Commander Pulse") that lets an operator ask questions/give guidance mid-incident; can trigger a full re-investigation if the guidance is materially state-changing. |

**How they connect:** `src/domain/agents/langgraph_investigator.py` wires
RCA → (Impact + Runbook in parallel) → Grounding Critic as an explicit
**LangGraph state graph** — this is a real dependency graph, not a linear
script, so it's easy to show visually and reason about.

---

## 5. The incident lifecycle (state machine)

Defined in `src/domain/state_machine.py`. Every transition is enforced in
code — an incident cannot skip a state:

```
DETECTED → CORRELATING → TRIAGING → INVESTIGATING → PLAN_READY
    → AWAITING_APPROVAL → EXECUTING → VERIFYING → RESOLVED
                              │            │
                              ▼            ▼
                    MANUAL_ACTION_REQUIRED  FAILED
```

- Any state can short-circuit to `RESOLVED` if an external monitor reports
  the issue self-healed (clearly audit-tagged as "resolved externally, not
  by an executed NemoGuard plan").
- `RESOLVED`, `FAILED`, `CANCELLED` are terminal — no incident can be
  "un-resolved" or silently reopened.
- A **4-hour approval timeout** automatically escalates an unattended plan
  back into active investigation (via a durable Temporal workflow timer) —
  no incident silently rots waiting on a human who never shows up.

---

## 6. The safety model — this is the part leadership will care about most

This is deliberately **not** "let the AI do whatever it wants." Three
independent layers:

1. **Human-in-the-loop approval.** Any plan step above LOW risk requires
   explicit human sign-off before execution (`AutonomyMode.HUMAN_APPROVAL_REQUIRED`
   in `src/capabilities/models.py`). The system will not auto-execute a
   database cleanup or a job rerun on its own.
2. **Governed Capability Gateway** (`src/capabilities/`). The AI never gets
   raw shell/API access. Every possible action is a pre-registered,
   reviewed "capability" (e.g. `data.cleanup_partial_write`,
   `queue.quarantine_poison_message`, `compute.rerun_ingest_job`,
   `aws.glue.start_job_run`) with:
   - a **precondition check** (refuses to run if the situation doesn't
     actually call for it — e.g. refuses to "clean up a partial write" if
     the table isn't actually stale)
   - the actual **execute** call
   - an **independent verify** step that re-queries real system state
     afterward — it never trusts its own "I did it" claim.
   - If a plan proposes something with no matching registered capability,
     it is routed to `MANUAL_ACTION_REQUIRED` for a human — it is **never**
     silently skipped or fabricated as done.
3. **Independent verification before resolution.** An incident is only
   marked `RESOLVED` if the verification step genuinely passed against real
   system state. This was specifically benchmarked: across a live 30-scenario
   validation suite, the **false-resolution rate was 0%** — nothing was ever
   marked resolved without a real, verified fix.

---

## 7. Durability & reliability (why this isn't a fragile demo script)

- **Temporal.io workflows** (`src/domain/workflows/incident_workflow.py`)
  drive the investigate → approve → execute lifecycle. If the API process
  crashes mid-incident, the workflow survives and resumes exactly where it
  left off — this was explicitly validated with a live restart test.
- **Postgres** is the system of record — every alert, hypothesis, plan,
  action, verification result, and audit event is a durable row, not an
  in-memory object.
- A **class-level lock + deterministic correlator** prevents two
  simultaneous webhook deliveries for the same failure from creating
  duplicate incidents.
- **Multi-tenancy and RBAC** are enforced end-to-end (JWT auth, tenant
  scoping on every query, plan-hash integrity checks so an approval can't
  be replayed against a modified plan).

---

## 8. Backend project structure (`src/`)

```
src/
  api/                 FastAPI app: REST + SSE streaming endpoints, auth, webhook security
  domain/
    orchestrator.py    The central coordinator: webhook ingestion, correlation, triage kickoff
    state_machine.py   Enforced incident lifecycle transitions
    correlator.py       Deterministic alert->incident matching (run_id/topology/time proximity)
    incident_state_service.py   Safe, audited state transitions
    impact_engine.py    Deterministic business-risk/SLA scoring (never LLM-guessed)
    agents/             All AI agents (see section 4)
    workflows/           Temporal workflow definitions
    activities/           Temporal activities (triage, execution, lifecycle transitions)
    commander/            Commander Live conversational engine
    memory/               "Incident Memory" — learns from past resolved incidents
    evaluation/           Scored validation benchmark (ground truth, scoring, RCA accuracy)
    notifications/         Outbound Teams/webhook incident notifications
    replay/                Historical incident replay for demos/training
  capabilities/          Governed action registry, execution engine, plan compiler
  store/                 Postgres access layer + schema
  tools/                  Read/write tool contracts used by agents
```

## 9. Frontend structure (`frontend/src/`)

React + Vite + TailwindCSS SPA:

```
pages/
  LandingPage/            Marketing/overview page
  LoginPage/              Auth
  IncidentsPage/          Main incident queue + workspace (the primary operator screen)
  AgentOperationsPage/    Live Agent Operations Console (real-time SSE trace of agent reasoning)
  IntelligencePage/       Incident Memory / cross-incident learning views
  AdoptionReadinessPage/  Rollout/adoption metrics dashboard
  ScenarioCockpitPage/    Demo/testing control surface for triggering real simulated failures
  SettingsPage/           Admin/user settings

components/
  dashboard/              The incident workspace itself:
                            SituationHeader, IncidentQueue, InvestigationPanels,
                            RecoveryRail, EvidenceModal, CommanderPanel,
                            CancelIncidentModal, WorkspaceTabs
  AgentConstellation.tsx  Live visual of which agent is currently active
  LiveOperationsConsole.tsx  Streaming agent reasoning/tool-call trace
  PlanApprovalModal.tsx  The human approval gate UI

hooks/
  useIncidentEvents.ts    SSE subscription — live updates as agents work, no polling
  useIncidentData.ts      REST data fetching for incident details
  useCommander.ts         Commander Live chat integration
```

Real-time updates are pushed via **Server-Sent Events (SSE)** — when an
agent starts reasoning, calls a tool, or finishes, the UI updates live
without polling, which is a strong visual for a demo (you can literally
watch the AI "think").

---

## 10. Infrastructure & how it runs

```
docker-compose.yml services:
  api                FastAPI backend (built from Dockerfile.api)
  frontend            React/Vite dev server
  postgres            System of record
  temporal            Workflow durability engine
  temporal-worker     Executes Temporal activities (triage, execution)
  simulator            "Scenario Lab" — LocalStack-backed AWS simulator used to
                        generate REAL Lambda/S3/CloudWatch/SQS failures for demos
                        and the validation benchmark (not fake canned data)
```

The **Scenario Lab / LocalStack simulator** is a notable technical
differentiator worth calling out live: demo failures aren't scripted mock
JSON — they are real AWS Lambda invocations that genuinely throw, real S3
objects with genuinely malformed content, real CloudWatch alarms that
genuinely trip. The agents are investigating real infrastructure state,
not a canned story.

---

## 11. Governance, safety & validation evidence (proof points for leadership)

- **WP-029-001 Scored Validation Benchmark**
  (`src/domain/evaluation/`, `scripts/run_scored_validation.py`): an
  automated suite that live-triggers real failure scenarios, waits for the
  actual multi-agent pipeline to run, and scores the REAL persisted
  results against ground truth — RCA accuracy, correlation accuracy,
  terminal-state accuracy, and **false-resolution rate**.
  - Most recent full run: **RCA top-1 accuracy 60%, top-3 accuracy 60%,
    false-resolution rate 0%** across live scenarios (see
    `docs/validation/scored_validation_run_2026-08-31_findings.md`).
  - This is a genuine, repeatable, live-system benchmark — not a
    marketing number. It has also been used to find and fix real
    production bugs (e.g. a database-connection leak, discovered because
    the benchmark's own false-resolution safety net kept working correctly
    even while other things broke).
- **Multi-tenancy & RBAC** validated live (WP-VAL-003/005).
- **Temporal durability** validated with a live process-restart test —
  in-flight incidents survive a crash.
- **Plan-hash integrity**: an approval is cryptographically tied to the
  exact plan content, so a plan cannot be silently altered between
  proposal and approval.

---

## 12. What to actually demo live

1. **Scenario Cockpit page** → trigger a real failure (e.g. schema drift).
2. **Agent Operations page** → watch the live SSE trace: Watcher classifies
   the alert → RCA agent calls real tools (logs, CloudWatch) → Impact/
   Runbook run → Grounding Critic verifies and either passes or flags a
   safety concern.
3. **Incidents page** → the resulting incident: root cause, evidence,
   hypothesis ledger, business impact, proposed recovery plan with risk
   levels.
4. **Approve the plan** → watch it execute through the Capability Gateway
   → watch independent verification run → incident flips to RESOLVED (or,
   if verification fails, correctly stays open/escalates — a good moment
   to explicitly point out the system does NOT lie about success).
5. **Commander Pulse / Commander Live** → ask the AI a question mid-incident
   as a live conversational moment.

---

## 13. One-slide summary (verbatim-ready)

> **NemoGuard** is a multi-agent AI system that autonomously detects,
> investigates, and proposes verified fixes for data pipeline incidents —
> with mandatory human approval for any real action, a governed capability
> layer instead of raw AI access, independent post-action verification, and
> a full audit trail. Built on FastAPI, Postgres, Temporal (for
> crash-durable workflows), LangGraph (for the multi-agent reasoning
> graph), and NVIDIA Nemotron LLMs. Validated with a live, repeatable
> benchmark suite — 0% false-resolution rate across real triggered
> failures.
