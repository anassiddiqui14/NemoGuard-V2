# NemoGuard Pipeline Copilot — Current Architecture & Detailed Design Document

**Status:** As-built, current state (hackathon/prototype implementation)
**Scope:** `pipeline-copilot/` application (backend, frontend, simulator, orchestration, data layer)
**Audience:** Engineers extending, operating, or evaluating the current system

> This document describes the system **as it is implemented today** in this repository. For the future/enterprise target architecture, see `nemoguard_enterprise_productization_roadmap.md`. For narrower prior write-ups, see `docs/system_architecture.md`, `docs/agent_architecture.md`, and `docs/nemoclaw_network_and_architecture.md` (this document supersedes and consolidates all three with full technical detail, including code-level behavior).

---

## 1. Executive Summary

NemoGuard Pipeline Copilot is an **agentic incident-response platform for data pipeline operations**. It ingests alerts (via webhook or a synthetic scenario simulator), correlates them into incidents, runs a multi-agent AI investigation (root cause analysis, downstream impact analysis, runbook retrieval, and a grounding/safety critic) powered by **NVIDIA Nemotron** models, and produces a structured recovery plan. A human operator reviews the plan in a React dashboard, approves or rejects it (with feedback used to re-plan), and the system "executes" and "verifies" the recovery (currently simulated at the persistence layer).

The system is composed of five deployable units, orchestrated with Docker Compose:

| Component | Technology | Role |
|---|---|---|
| `postgres` | PostgreSQL 15 | Single source of truth for all incident, evidence, plan, and audit data |
| `temporal` | Temporal (dev server) | Durable workflow engine for the incident lifecycle |
| `api` | FastAPI (Python) | REST + SSE API, webhook ingestion, orchestration entrypoints |
| `temporal-worker` | Temporal Python SDK worker | Executes the `IncidentLifecycleWorkflow` (triage + execution activities) |
| `frontend` | React + Vite + TypeScript + Tailwind | "NemoGuard Command Center" operator dashboard |
| `simulator` | FastAPI (Python) | "Scenario Lab" — injects synthetic/AI-generated incidents via webhooks |

A large vendored subdirectory, `nemoclaw_repo/`, is NVIDIA's open-source **NemoClaw** project (a sandboxed AI-agent CLI/runtime toolkit) — it is **not currently wired into the running application**; the actual agent logic in this project is implemented natively in Python (`src/domain/agents/*`) using direct NVIDIA NIM API calls, LangGraph, and a custom tool-calling loop. Its presence in the repo appears to be reference material / branding inspiration for the "NemoClaw Agent Network" concept described in the docs, not an active runtime dependency.

---

## 2. High-Level Architecture Diagram

```mermaid
flowchart TB
    subgraph Clients
        UI[React Dashboard\n(frontend/)]
        SIMUI[Scenario Lab UI\n(simulator-frontend/)]
    end

    subgraph SimulatorBackend[Simulator Backend :8001]
        SIM[FastAPI Simulator]
    end

    subgraph APIService[API Service :8000]
        FASTAPI[FastAPI app main.py]
        AUTH[JWT Auth - api/auth.py]
        ORCH[IncidentOrchestrator]
        WATCHER[WatcherAgent]
        CORR[CorrelatorEngine]
    end

    subgraph TemporalCluster[Temporal :7233 / :8233]
        TWF[IncidentLifecycleWorkflow]
    end

    subgraph Worker[temporal-worker]
        TRIAGE[triage_incident_activity]
        EXEC[execute_plan_activity]
        INVEST[LangGraphInvestigator]
    end

    subgraph Agents[Native Python Agents - NVIDIA NIM]
        RCA[RCAAgent]
        DEP[DependencyAgent]
        RUN[RunbookAgent]
        CMD[CommanderAgent]
        CRITIC[GroundingCritic]
    end

    subgraph DB[(PostgreSQL)]
        PG[(nemoguard_db)]
    end

    SIMUI -->|POST /trigger, /trigger/ai| SIM
    SIM -->|writes logs/assets/runbooks| PG
    SIM -->|POST /api/v2/ingest/webhook| FASTAPI

    UI -->|REST /api/v2/*| FASTAPI
    UI -->|SSE /events/stream| FASTAPI

    FASTAPI --> AUTH
    FASTAPI --> ORCH
    FASTAPI -->|webhook| WATCHER
    ORCH --> CORR
    FASTAPI -->|start_workflow / signal| TWF
    TWF -->|execute_activity| TRIAGE
    TWF -->|execute_activity| EXEC
    TRIAGE --> INVEST
    INVEST --> RCA
    INVEST --> DEP
    INVEST --> RUN
    INVEST --> CRITIC
    RCA -.tool calls.-> PG
    DEP -.tool calls.-> PG
    RUN -.tool calls.-> PG
    RCA & DEP & RUN & CRITIC -->|HTTPS| NIM[(NVIDIA NIM API\nnemotron-3-super-120b-a12b)]
    CMD -.unused directly - logic folded into orchestrator/critic.-> PG

    FASTAPI <--> PG
    ORCH <--> PG
    TRIAGE <--> PG
    EXEC <--> PG
```

---

## 3. Repository Layout (relevant paths)

```
pipeline-copilot/
├── docker-compose.yml            # 6-service orchestration
├── Dockerfile.api                # FastAPI image
├── Dockerfile.temporal            # Temporal worker image
├── migrations/002_domain_model.sql   # Full domain schema (authoritative)
├── config/                       # action_policy.yaml, demo.yaml, scoring.yaml (declared, not fully wired)
├── data/
│   ├── mock_dimensions/cmdb.json, runbooks.json   # Static reference data used as fallback context
│   ├── seed/                    # CSV/YAML seed data (jobs, dependencies, business assets, runbooks)
│   └── generated/                # Legacy SQLite artifacts (ground_truth.json, pipeline.db) — mostly unused now that Postgres is primary
├── src/
│   ├── api/
│   │   ├── main.py               # FastAPI app + all REST/SSE endpoints
│   │   ├── auth.py               # JWT-based auth (JWT_SECRET, mock login)
│   │   └── mcp_server.py         # FastMCP server exposing ReadTools (SQLite-backed, legacy/standalone)
│   ├── domain/
│   │   ├── models.py             # Pydantic domain models (Incident, Evidence, Hypothesis, ActionPlan, etc.)
│   │   ├── enums.py              # IncidentState, ToolRisk, Severity, HypothesisStatus
│   │   ├── state_machine.py      # Valid incident state transition rules
│   │   ├── correlator.py         # CorrelatorEngine: fingerprinting + pairwise scoring + clustering
│   │   ├── orchestrator.py       # IncidentOrchestrator: triage, fallback triage, plan save, feedback, webhook processing
│   │   ├── agents/
│   │   │   ├── base_agent.py     # BaseAgent: NVIDIA NIM client, call_llm_json, call_llm_with_tools
│   │   │   ├── agent_tools.py    # query_logs / get_cmdb_context / get_runbook (Postgres-backed tool functions + schema)
│   │   │   ├── rca_agent.py      # RCAAgent (tool-calling)
│   │   │   ├── dependency_agent.py # DependencyAgent (tool-calling)
│   │   │   ├── runbook_agent.py  # RunbookAgent
│   │   │   ├── commander_agent.py# CommanderAgent (synthesis - currently secondary path)
│   │   │   ├── watcher_agent.py  # WatcherAgent (webhook triage/correlation classifier)
│   │   │   └── langgraph_investigator.py # LangGraph StateGraph: parallel RCA/Impact/Runbook + GroundingCritic
│   │   ├── activities/
│   │   │   ├── triage_activity.py    # Temporal activity wrapping orchestrator.triage_incident
│   │   │   └── execution_activity.py # Temporal activity wrapping orchestrator.execute_plan
│   │   ├── workflows/incident_workflow.py # IncidentLifecycleWorkflow (Temporal @workflow.defn)
│   │   └── connectors/           # airflow_connector.py, datadog_connector.py (stubs/placeholders)
│   ├── generator/                # Synthetic dataset generation (topology, healthy_runs, log_factory, scenario_injection, validators)
│   ├── store/
│   │   ├── postgres_database.py  # PostgresDatabase: connection wrapper, schema init, seed loaders, stats/reset
│   │   ├── database.py           # Legacy SQLite database class (superseded by Postgres)
│   │   └── schema.sql            # Legacy/base schema (superseded by migrations/002_domain_model.sql)
│   ├── tools/
│   │   ├── contracts.py, base.py # Tool contract base types
│   │   ├── registry.py           # ToolRegistry + ToolDefinition + policy-enforced execute_tool()
│   │   ├── read_tools.py         # ReadTools class used by mcp_server.py (SQLite-oriented, legacy path)
│   │   └── write_tools.py        # Action/write tool stubs
│   ├── ui/                       # Older Streamlit-era UI code (alert_streamer.py, app.py, incident_commander.py) — superseded by React frontend
│   ├── utils/telemetry.py        # OpenTelemetry setup helper
│   └── temporal_worker.py        # Worker entrypoint (registers workflow + activities)
├── frontend/                     # React 18 + Vite + TS + Tailwind operator dashboard
│   └── src/
│       ├── App.tsx                # Top bar + shell
│       ├── components/
│       │   ├── Dashboard.tsx      # Main 3-pane command center
│       │   ├── AgentConstellation.tsx  # Visual agent-activity graphic
│       │   ├── LiveOperationsConsole.tsx # SSE-driven audit event terminal
│       │   └── PlanApprovalModal.tsx # Plan review / approve / reject+feedback modal
│       └── hooks/useIncidentData.ts # Polling hook for evidence/hypotheses/plans/impact/alerts
├── simulator_backend/main.py     # "Application Simulator" — generates + injects synthetic incidents
├── simulator-frontend/           # Simulator's own React control panel
└── nemoclaw_repo/                # Vendored NVIDIA NemoClaw OSS project (sandboxed agent CLI) — NOT wired into the running app
```

---

## 4. Data Layer

### 4.1 Database: PostgreSQL

The system uses a single PostgreSQL database (`nemoguard_db`) as the sole persistent store. There is **no SQLite in the running Docker stack** — earlier SQLite-oriented code (`src/store/database.py`, `src/store/schema.sql`, `src/tools/read_tools.py`, `src/api/mcp_server.py`) remains in the repo as legacy/standalone tooling but is not used by `main.py`/`orchestrator.py` at runtime.

- **Connection:** `PostgresDatabase` (`src/store/postgres_database.py`) wraps `psycopg2` connections in a context manager (`get_connection()`), auto-committing on success and rolling back on exception.
- **Schema bootstrap:** On FastAPI startup (`main.py::startup_event`), the app checks whether the `incident` table exists in `public` schema; if not, it runs `db.init_schema()`, which executes `src/store/schema.sql` followed by `migrations/002_domain_model.sql`. The migration **drops and recreates** `incident`, `incident_alert`, `approval`, `audit_event`, and `action_plan` tables to establish the authoritative domain model on top of the legacy seed schema.

### 4.2 Schema Overview

**Seed / reference tables** (from `schema.sql`):
- `job`, `dependency` — pipeline topology (jobs + parent/child edges)
- `business_asset`, `asset_dependency` — legacy business-impact mapping (superseded in practice by `data_asset`/`incident_impact` from the migration)
- `execution` — pipeline run records (`run_id`, `job_id`, status, timing, `incident_id`)
- `log_event` — structured log lines per run (`level`, `component`, `error_code`, `message`)
- `alert` — raw/normalized alerts (`severity`, `alert_type`, `source_system`, `message`, `status`)

**Domain model tables** (from `migrations/002_domain_model.sql` — the actively used schema):
- `incident` — primary aggregate: id, title, summary, `status` (IncidentState), severity, primary_job_id/run_id, owner_team, timestamps, `correlation_confidence`, `rca_confidence`, `next_sla_breach_at`, `actual_root_cause`, `resolution_summary`, optimistic-lock `version`
- `incident_alert` — many-to-many incident↔alert with `correlation_score` and `correlation_reasons_json`
- `agent_run`, `agent_step`, `tool_call` — designed for full AI observability (agent invocation, step, and tool-call tracing); **partially used** — orchestrator inserts a placeholder `SYSTEM`/`RCA-Agent`/`Commander` row into `agent_run` as a foreign-key anchor but does not populate `agent_step`/`tool_call` in the current code path
- `evidence` — evidence items with `evidence_type`, `source_system`, `title`, `excerpt`, `collected_at`
- `hypothesis` — root-cause hypotheses with `cause_type`, `confidence`, `status`, JSON-encoded evidence ID arrays
- `data_asset`, `asset_dependency` (redefined), `incident_impact` — business/technical blast-radius model actually used by the API and orchestrator (note: `asset_dependency` is redefined by the migration with a different shape than the seed-schema version — this is a known schema-evolution inconsistency)
- `deployment`, `schema_version` — modeled for deployment/schema-change correlation but **not populated** by any current code path (forward-looking columns)
- `runbook`, `runbook_step` — operational runbooks; populated by the simulator (`simulator_backend/main.py`) and read by `agent_tools.get_runbook()`
- `action_plan`, `action_step` — the AI-generated recovery plan and its steps; central to the approval/execution flow
- `approval` — human approval/rejection records, linked to `action_plan_id` and a `plan_hash`
- `action_execution`, `verification_result` — modeled for granular execution/verification tracking; `verification_result` **is** populated (two hardcoded checks) by `orchestrator.execute_plan()`, but `action_execution` is not currently written
- `feedback` — modeled for post-incident structured feedback; not currently populated (the live "feedback" loop instead re-writes the `action_plan`/`action_step` rows directly — see §7.5)
- `audit_event` — append-only-in-practice event log (actor, event_type, event_summary, `created_at`) — the backbone of the live "Agent Activity & Tool Trace" UI panel via SSE

### 4.3 Data Model Notes / Gaps vs. Documentation

- The Pydantic models in `src/domain/models.py` (`Incident`, `Evidence`, `Hypothesis`, `ActionPlan`, `ActionStep`, `Approval`, `ActionExecution`, `VerificationResult`, `AuditEvent`, `AgentRun`) map closely to the migration schema, confirming the migration is the intended domain contract. However, the FastAPI endpoints in `main.py` largely bypass these Pydantic models for reads — they execute raw SQL and manually zip column names to values into plain dicts. This means response shapes are **not strictly typed/validated at the API boundary** today.
- `incident.status` values are free-form strings; `IncidentState` enum values (`DETECTED`, `CORRELATING`, `TRIAGING`, `INVESTIGATING`, `PLAN_READY`, `AWAITING_APPROVAL`, `EXECUTING`, `VERIFYING`, `RESOLVED`, `ROLLED_BACK`, `FAILED`, `CANCELLED`) are used inconsistently — e.g., the webhook path sets a newly created incident directly to `INVESTIGATING`, skipping `DETECTED`/`CORRELATING` explicitly, and `severity` values written by the simulator use a `SEV-1`/`SEV-2` string convention while the `Severity` enum defines `SEV_1`/`SEV_2` (underscore) — the `/api/v2/overview` endpoint's SQL filters (`severity = 'SEV-1'`) match the simulator's convention, not the enum's.
- `src/domain/state_machine.py` defines valid state transitions but is **not invoked** by `orchestrator.py` or `main.py` — transitions are applied via direct `UPDATE incident SET status = ...` statements without going through the state machine's validation.

---

## 5. Incident Ingestion & Correlation

### 5.1 Two Ingestion Paths

**Path A — Simulator-driven (primary demo path).** The `simulator_backend` service (`simulator_backend/main.py`) exposes:
- `POST /trigger` — deterministic canned scenarios: `SCHEMA_REGRESSION`, `OOM_CRASH`, `CASCADING_FAILURE`, or a generic fallback. Each scenario hardcodes realistic failure logs, webhook payloads (Datadog/Airflow/PagerDuty/Sentry-style), and (for `CASCADING_FAILURE`) seeds CMDB jobs, dependency edges, and a runbook directly into Postgres.
- `POST /trigger/ai` — a streaming (`text/event-stream`) endpoint that calls the NVIDIA NIM API directly (model `nvidia/nemotron-3-super-120b-a12b`, `response_format: json_object`) with a free-text operator prompt, asking the LLM to invent a full synthetic incident (failure logs, webhook payloads, business assets, runbooks) matching a fixed JSON schema. The generated data is inserted into Postgres, then each generated webhook payload is POSTed to the API's `/api/v2/ingest/webhook`.
- Both paths first call `generate_noise_logs()` to inject ~150 benign `INFO`-level log lines from fake services, ensuring RCA agents must actually filter signal from noise rather than being handed only the failure.
- `POST /reset` — truncates `incident` and `alert` tables (cascading).

**Path B — Direct webhook ingestion (production-shaped path).** External callers (or the simulator) `POST /api/v2/ingest/webhook` with an arbitrary JSON payload. This is handled by `IncidentOrchestrator.process_webhook()`:
1. Fetches all currently active incidents (status not in `RESOLVED`/`CLOSED`/`CANCELLED`).
2. Calls `WatcherAgent.analyze(payload, active_incidents)` — an LLM call (Nemotron) that classifies whether the payload is a real signal or noise, normalizes it into a canonical alert schema, and optionally proposes a `correlated_incident_id` if it believes the alert belongs to an existing incident (using the LLM's own judgment over run_id/topology/temporal proximity — i.e., **correlation here is LLM-driven, not the deterministic `CorrelatorEngine`**).
3. If `is_valid` is false → the alert is dropped (`status: "ignored"`).
4. If the Watcher proposes a valid `correlated_incident_id` matching an active incident → the alert is inserted and linked via `incident_alert`, incident `summary` is appended, and an audit event is logged. No new investigation is triggered.
5. Otherwise, if severity is `high`/`critical` → a **new incident is created** using `CorrelatorEngine.create_incident()` (deterministic path — see §5.2) with status set directly to `INVESTIGATING`, `next_sla_breach_at` = now+30min.
6. Otherwise → the alert is stored standalone with no incident.
7. `main.py`'s `/api/v2/ingest/webhook` handler then starts a `IncidentLifecycleWorkflow` Temporal workflow for any newly created incident.

### 5.2 CorrelatorEngine (Deterministic — Present but Underused)

`src/domain/correlator.py` implements a fully deterministic, non-LLM correlation engine:
- **Fingerprinting:** SHA-256 hash of `source_system:run_id:alert_type:hour_bucket` for deduplication.
- **Pairwise scoring:** weighted combination of (a) same `run_id` (+0.8), (b) time proximity ≤60s (+0.3) or ≤300s (+0.15), (c) same `alert_type` (+0.2), (d) topology adjacency via a CMDB edge list loaded from `data/mock_dimensions/cmdb.json` (+0.6, capped).
- **Clustering:** greedy — pick highest-severity unassigned alert as primary, absorb all alerts scoring ≥ `min_cluster_score` (default 0.6), repeat.
- **`create_incident()`** builds an `Incident` Pydantic object with a generated summary citing correlation reasons and duplicate counts, severity mapped from the primary alert's severity string.

**Current usage:** `CorrelatorEngine` is only invoked from inside `orchestrator.process_webhook()` for the "new incident" branch, and only to construct the `Incident` object for a **single-alert cluster** (`cluster = {"primary_alert": alert_obj, "alerts": [alert_obj], ...}`) — i.e., the multi-alert clustering logic (`correlate()`) is defined but not called anywhere in the live request path today. Real multi-alert correlation in the running system is effectively delegated to the `WatcherAgent`'s LLM judgment (step 5.1.2 above), not the deterministic engine.

---

## 6. Agentic Investigation Layer

### 6.1 Two Parallel Investigation Implementations

The codebase contains **two independent implementations** of the multi-agent investigation, both wired to run, with the LangGraph version taking priority:

1. **`LangGraphInvestigator`** (`src/domain/agents/langgraph_investigator.py`) — the primary path, invoked by `orchestrator.triage_incident()`.
2. **`triage_fallback()`** (inside `orchestrator.py`) — a simpler sequential fallback invoked automatically if the LangGraph path raises an exception or doesn't successfully save a plan.

There is also a **third, older/unused synthesis path**: `CommanderAgent` (`commander_agent.py`) and the orchestrator's own `call_llm_json()` + `_save_dynamic_triage()` method, which implement a single-shot "ask the LLM for the whole plan in one JSON blob" approach. This appears to be an earlier iteration that has been superseded by the LangGraph graph but was not deleted; `triage_feedback()` (the human-rejection re-planning path) still uses this direct single-call approach rather than re-invoking LangGraph.

### 6.2 BaseAgent — Shared LLM Integration

All native agents inherit from `BaseAgent` (`src/domain/agents/base_agent.py`):
- **Model:** `nvidia/nemotron-3-super-120b-a12b`, called via the OpenAI-compatible `AsyncOpenAI` client against `https://integrate.api.nvidia.com/v1`.
- **`call_llm_json(prompt)`** — streams the completion (`stream=True`), accumulates content, strips Markdown code fences, and `json.loads()`s the result. Uses `extra_body={"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 16384}` to enable Nemotron's reasoning mode; reasoning tokens are printed to stdout for debugging but not persisted.
- **`call_llm_with_tools(prompt, tools, execute_tool_fn)`** — implements a manual ReAct-style tool-calling loop (max 5 iterations): sends the tool schema, and if the model responds with `tool_calls`, executes each via the provided callback and appends `role: tool` messages, looping until the model returns a final content-only JSON message.
- **API key** is hardcoded as a fallback default directly in source (`NVIDIA_API_KEY` env var takes precedence) — a hardcoded key also appears in `orchestrator.py` and `docker-compose.yml`. This is a **notable security gap** (see §11).

### 6.3 The LangGraph Investigation Graph

`LangGraphInvestigator` builds a `StateGraph[InvestigationState]` with the following topology:

```
START ──▶ rca ──────────┐
START ──▶ impact ───────┼──▶ critic ──▶ END
START ──▶ runbook ──────┘
```

- **`rca` node** → calls `RCAAgent.analyze(incident_id)`
- **`impact` node** → calls `DependencyAgent.analyze(f"Investigating incident {incident_id}")` (note: passes only a generic string, not the RCA finding, because it runs in parallel with RCA rather than after it — this differs from the sequential dependency described in `docs/agent_architecture.md`, which states the Dependency Agent should receive the RCA finding)
- **`runbook` node** → calls `RunbookAgent.analyze(alerts)`
- **`critic` node** → `GroundingCritic.analyze(rca_result, impact_result, runbook_result)` — synthesizes and validates all three branches into one `final_plan`

`InvestigationState` is a `TypedDict` carrying `incident_id`, `alerts`, and each branch's raw result dict, plus `critic_passed`, `critic_feedback`, `final_plan`.

`investigate()` drives the graph with `graph.astream(state)`, and for each node's emitted update fires an `audit_callback(incident_id, actor, event_type, summary)` — this is exactly how live audit events (visible in the "Agent Activity & Tool Trace" console) get created during a real investigation: `RCA Agent → HYPOTHESIS_CREATED`, `Impact Agent → IMPACT_CALCULATED`, `Runbook Agent → RUNBOOK_RETRIEVED`, `Safety Agent → SAFETY_VALIDATION_PASSED/FAILED`.

**Note:** the graph has no evidence-sufficiency retry loop (unlike the target architecture's "request more evidence" cycle described in the roadmap) — each branch runs exactly once regardless of confidence, and there is no `NEEDS_HUMAN_INVESTIGATION` outcome if the critic fails; a failed critic still returns whatever `final_plan` the LLM produced.

### 6.4 Individual Agents

| Agent | File | Tools | Behavior |
|---|---|---|---|
| **RCAAgent** | `rca_agent.py` | `query_logs`, `get_cmdb_context`, `get_runbook` (via `agent_tools.AGENT_TOOLS_SCHEMA`) | Instructed to call `query_logs` once, then return `{finding, cause_type, confidence, evidence[]}` |
| **DependencyAgent** | `dependency_agent.py` | same tool schema | Instructed to call `get_cmdb_context` and return `{finding, impacts[]}` (`asset_id`, `impact_type`, `status`, `reason`) |
| **RunbookAgent** | `runbook_agent.py` | (not fully inspected in this pass, but follows the same `BaseAgent` pattern) | Matches alerts to operational runbooks |
| **CommanderAgent** | `commander_agent.py` | — | Legacy single-shot synthesizer; superseded by `GroundingCritic` in the live path |
| **WatcherAgent** | `watcher_agent.py` | none (pure `call_llm_json`) | Classifies webhook validity + correlation (see §5.1) |
| **GroundingCritic** | defined inline in `langgraph_investigator.py` | none | Combines the three branch outputs into `{passed, feedback, final_plan}` |

### 6.5 Tool Layer Used by Agents — `agent_tools.py`

`src/domain/agents/agent_tools.py` defines three concrete, Postgres-backed functions exposed to the LLM as OpenAI-style function-calling tools:
- **`query_logs(incident_id, keyword="")`** — resolves `incident.primary_run_id`, then queries `log_event` for `ERROR`/`WARN` rows (or keyword-filtered rows), limit 50.
- **`get_cmdb_context(service_name)`** — fuzzy-matches `job` by name/id, then joins `asset_dependency` → `business_asset` to return downstream assets; falls back to returning the first 5 `business_asset` rows if no match, so the LLM always has *something* to reason over.
- **`get_runbook(service_name)`** — fuzzy-matches `runbook` by title/id; falls back to the first 3 runbooks if no match.

All three tools are wrapped by `execute_tool_call(tool_name, arguments)`, the dispatcher passed into `call_llm_with_tools`. This is a **direct, in-process, unauthenticated function-calling implementation** — it is conceptually similar to the MCP pattern described in the documentation, but is not actually MCP (Model Context Protocol); the real `fastmcp`-based server (`src/api/mcp_server.py`) is a separate, unconnected implementation using `ReadTools`/SQLite.

### 6.6 Governed Tool Registry (Defined, Not Wired to Agents)

`src/tools/registry.py` implements a more rigorous `ToolRegistry`/`ToolDefinition`/`execute_tool()` pattern with Pydantic input/output validation and `ToolRisk`-based policy enforcement (`PolicyViolationError` for `PROHIBITED` tools or unapproved `HIGH`/`MEDIUM` risk tools). **This registry is not used by any of the live agents** (`rca_agent.py`, `dependency_agent.py`, etc. call `agent_tools.py` functions directly, bypassing risk/approval checks entirely). It represents the more production-grade tool-governance model described in the roadmap but is currently dead code in terms of the live request path.

---

## 7. Orchestration & Workflow Layer

### 7.1 Temporal Workflow

`IncidentLifecycleWorkflow` (`src/domain/workflows/incident_workflow.py`) is a `@workflow.defn` class with a single `run(incident_id)` entrypoint:

1. Executes `triage_incident_activity` (timeout 5 min) — this activity internally calls `IncidentOrchestrator.triage_incident()`.
2. If triage did not report `status == "EXECUTED"` and `saved_plan == True`, the workflow returns early with `{"status": "failed"}`.
3. Otherwise, it calls `workflow.wait_condition(lambda: self.approval_decision is not None)` — an **indefinite durable wait** for a human decision.
4. A `@workflow.signal(name="approve_plan")` handler (`approve_plan(signal_data)`) sets `self.approval_decision` and `self.plan_id` when the API sends a signal.
5. On `"approve"` → executes `execute_plan_activity` (timeout 5 min), which calls `IncidentOrchestrator.execute_plan()`.
6. On anything else → the workflow completes with `{"action": "cancelled"}` — **note: there is no signal path to feed back the "revise plan"/feedback flow into the running workflow.** The rejection+feedback path (`POST /api/v2/incidents/{id}/feedback`) calls `orchestrator.triage_feedback()` directly via a synchronous FastAPI request handler, entirely outside of Temporal — meaning a revised plan does not restart or continue the same workflow instance; the original workflow keeps waiting on the same signal condition until an eventual `approve`/other decision arrives.

### 7.2 Temporal Activities

- **`triage_incident_activity`** (`src/domain/activities/triage_activity.py`) — thin wrapper delegating to `IncidentOrchestrator.triage_incident(incident_id)`.
- **`execute_plan_activity`** (`src/domain/activities/execution_activity.py`) — thin wrapper delegating to `IncidentOrchestrator.execute_plan(incident_id, plan_id)`.

### 7.3 Temporal Worker Process

`src/temporal_worker.py` connects to `TEMPORAL_URL` (default `localhost:7233`, overridden to `temporal:7233` in Docker) and runs a `Worker` on task queue `"incident-task-queue"`, registering `IncidentLifecycleWorkflow` and both activities. This runs as the separate `temporal-worker` container.

### 7.4 `IncidentOrchestrator.triage_incident()` — the Investigation Entry Point

1. Fetches all alerts joined to the incident from `alert`/`incident_alert`.
2. Instantiates `LangGraphInvestigator` and runs `investigator.investigate(incident_id, alerts_data, audit_callback=self._log_audit)` via `asyncio.run(...)`.
3. Maps the LangGraph `final_state` (rca_result, impact_result, runbook_result, final_plan) into the flat `llm_response` shape expected by `save_agent_findings()`.
4. Calls `save_agent_findings()`, which persists Evidence, Hypotheses, Impacts, an Action Plan, and Action Steps in a single transaction, then updates `incident.actual_root_cause`, `rca_confidence`, and `status = PLAN_READY`.
5. If the LangGraph path throws an exception, `saved_plan = False` and the orchestrator falls back to `triage_fallback()`.

### 7.5 Fallback Triage — `triage_fallback()`

A simpler, purely sequential path used when LangGraph fails:
1. Runs `RCAAgent.analyze(incident_id)` directly (no LangGraph, no parallelism).
2. Runs `DependencyAgent.analyze(hypothesis_statement)` — this time correctly passing the RCA finding as context (unlike the LangGraph parallel path).
3. Persists Evidence (from RCA tool results only — Dependency Agent's evidence is discarded), a Hypothesis, Impacts, and an **Action Plan with 4 hardcoded generic recovery steps** ("Rollback schema mapping to v118...", "Validate schema compatibility...", "Re-trigger customer_profile ingestion pipeline...", "Verify downstream job execution..."). These steps are **not derived from the LLM output at all** — they are static placeholder text regardless of the actual incident, which is a significant fidelity gap versus the documented "AI-generated technical runbook."
4. Logs 5 audit events including a synthetic "Safety Agent" and "Runbook Agent" pass that didn't actually run as separate agents in this path.

### 7.6 Human Feedback / Plan Revision Loop — `triage_feedback()`

When an operator rejects a plan with feedback text (`PlanApprovalModal.tsx` → `POST /api/v2/incidents/{id}/feedback`):
1. Fetches the most recent `action_plan` + its `action_step`s for the incident.
2. Builds a prompt embedding the user's `feedback_text` and the previous plan JSON, asking the LLM (via `orchestrator.call_llm_json()` — the **legacy raw `urllib`-based NIM caller**, not `BaseAgent`) to produce a revised plan matching a fixed schema.
3. Deletes old `action_step` rows and inserts new ones; bumps `action_plan.plan_version`, resets `status = 'PENDING_APPROVAL'`.
4. Logs a `PLAN_REVISED` audit event.

This is a complete, working "revise" loop, but it operates **outside of Temporal** (direct synchronous API call) and **outside of LangGraph** (single-shot prompt, no multi-agent re-investigation), so a revised plan does not re-run RCA/Impact/Runbook — it only asks the LLM to patch the existing plan text.

### 7.7 Plan Execution & Verification — `execute_plan()`

Invoked either by the Temporal `execute_plan_activity` (after an `approve` signal) or directly by `POST /api/v2/incidents/{id}/plans/{plan_id}/execute` (a manual override bypassing Temporal entirely):
1. Sets `action_plan.status = 'EXECUTED'` and **all** `action_step`s to `'SUCCEEDED'` unconditionally — there is no actual invocation of any tool, connector, or infrastructure mutation. This confirms the documentation's stated limitation: "Mocked Remediation."
2. Sets `incident.status = RESOLVED` (called twice in the method — a minor redundancy) and stamps `resolved_at`.
3. Inserts two hardcoded `verification_result` rows ("Schema validation" → PASSED, "Row count within tolerance" → PASSED) regardless of the actual plan content.
4. Logs `ACTION_COMPLETED`, `VERIFICATION_PASSED`, and `INCIDENT_RESOLVED` audit events.

---

## 8. API Layer (FastAPI)

### 8.1 Application Setup

`src/api/main.py` defines a single FastAPI app (`title="NemoGuard - Pipeline Incident Commander"`) with a global exception handler returning `{"error", "detail", "path"}` on any unhandled exception (HTTP 500). Every endpoint constructs a **new** `PostgresDatabase` instance per-request (no connection pooling / shared engine) using a hardcoded `POSTGRES_URL` default matching the Docker Compose service name `postgres`.

**Startup event (`startup_event`):**
- Initializes DB schema if `incident` table doesn't exist.
- Connects to Temporal (`Client.connect(TEMPORAL_URL)`) and stores the client in a module-level global `temporal_client`. If Temporal is unreachable, the app **still starts**, but all workflow-dependent endpoints silently degrade (e.g., `/triage` returns `{"accepted": False, "status": "NO_TEMPORAL_CLIENT"}` instead of failing).

### 8.2 Endpoint Inventory

**Status / overview**
- `GET /api/v2/status` — static health-ish payload (not a real health check of DB/Temporal)
- `GET /api/v2/overview` — dashboard KPI counts (open/critical/high incidents, alerts correlated) — note the `SEV-1`/`SEV-2` string mismatch flagged in §4.3 means `critical_incidents`/`high_incidents` counts can be silently wrong depending on which code path wrote the severity

**Incident reads**
- `GET /api/v2/incidents?state=open|all`
- `GET /api/v2/incidents/{id}`, `/summary` (alias of the same), `/hypotheses`, `/evidence`, `/impact`, `/plans` (includes nested steps), `/events` (full audit history), `/alerts`
- `GET /api/v2/alerts` — all alerts, unfiltered by tenant/incident

**Agent/LLM context endpoints** (`/api/v2/context/*`) — designed to expose read-only context to external MCP-style consumers: `alerts/{id}`, `logs/{id}`, `cmdb` (reads static `data/mock_dimensions/cmdb.json`), `runbooks` (reads static `runbooks.json`). These are **not used by the native agents** (which query Postgres directly via `agent_tools.py`) — they appear to be a leftover integration surface for an external NemoClaw agent process that would call back into the API.

**Workflow actions**
- `POST /api/v2/ingest/webhook` — entrypoint described in §5.1; starts Temporal workflow for newly created incidents
- `POST /api/v2/incidents/{id}/triage` — manually kicks off investigation via Temporal (sets status to `INVESTIGATING` first)
- `POST /api/v2/incidents/{id}/agent-findings` — allows externally POSTing a findings payload directly into `save_agent_findings()` (an integration point for an external agent, unused by the current native agents but consistent with the "NemoClaw agent posts back to API" pattern referenced in `docs/system_architecture.md`)
- `GET /api/v2/incidents/{id}/agent-logs` — reads a static log file `logs/{incident_id}_nemoclaw.log` if present (another vestige of an external NemoClaw process integration that isn't populated by the current Python agents)
- `POST /api/v2/incidents/{id}/feedback` → `triage_feedback()`
- `POST /api/v2/incidents/{id}/plans/{plan_id}/approve` — writes an `approval` row, sets `action_plan.status='APPROVED'`, logs audit event, and **if Temporal is connected**, signals the running workflow via `IncidentLifecycleWorkflow.approve_plan`; otherwise just returns `{"status": "success"}` without actually progressing the workflow (a gap if Temporal is down: the plan is marked approved in the DB but the Temporal workflow, if it exists, never receives the signal and will wait forever)
- `POST /api/v2/incidents/{id}/plans/{plan_id}/execute` — manual override calling `orchestrator.execute_plan()` directly, bypassing Temporal/approval-signal path entirely (this is the **actual path** used by `Dashboard.tsx`'s `handleExecute()`, since the frontend calls `/approve` not `/execute` — see §8.3 note below on the mismatch)

**Real-time stream**
- `GET /api/v2/incidents/{id}/events/stream` — SSE endpoint. Polls `audit_event` every 1 second (`asyncio.sleep(1)`) inside an infinite generator loop, tracking `last_ts` as a watermark, yielding new rows as `data: {...}\n\n` JSON events. No authentication is enforced on this endpoint (no dependency on `get_current_user`). Creates a **new DB connection every poll iteration** (not just once) — a minor inefficiency at scale.

### 8.3 Frontend/Backend Contract Nuance

`Dashboard.tsx`'s `handleExecute()` calls `POST /plans/{plan_id}/approve` (not `/execute`) with `{decision: "approve", plan_hash: "ui-approved"}`. The `/approve` endpoint only signals Temporal (or no-ops if Temporal is down) — it does **not** itself call `execute_plan()`. This means the actual "execute" logic only runs if: (a) Temporal is connected, (b) a live `IncidentLifecycleWorkflow` instance for that incident is still waiting on the signal, and (c) that workflow's activity call to `execute_plan_activity` succeeds. If any of these are not true (e.g., Temporal was down when the incident was created, or the workflow already completed/timed-out), clicking "Approve & Execute" in the UI will mark the plan `APPROVED` in the database but the incident will **never transition to `RESOLVED`** — a real gap in the current implementation given Temporal's dev-mode nature and the workflow's reliance on a still-live signal wait.

### 8.4 Authentication

`src/api/auth.py` implements JWT (HS256) issuance/validation:
- `create_access_token()` / `get_mock_token(role)` — a `/api/v2/auth/mock-login?role=...` endpoint issues a 1-day token for any requested role (no password/credential check at all — pure mock).
- `get_current_user()` — `HTTPBearer` dependency decoding the JWT into a `User` model (`user_id`, `email`, `roles`, `tenant_id`, `workspace_id`).
- `require_role(role)` — dependency factory; `admin` role bypasses all checks.
- **Critically, none of the actual incident/plan/webhook endpoints in `main.py` use `Depends(get_current_user)` or `Depends(require_role(...))`.** The entire auth module is defined and functional but **not enforced anywhere in the live API** — every endpoint is effectively open. The frontend's `handleExecute()` even sends a hardcoded `'Authorization': 'Bearer test-token'` header that isn't validated by the receiving endpoint (which has no auth dependency).

---

## 9. Frontend Architecture

### 9.1 Stack

React 18 + TypeScript + Vite + Tailwind CSS, with `framer-motion` for animation, `recharts` for the business-impact radar chart, `lucide-react` for icons, `react-hot-toast` for notifications (declared but not actively triggered — see `Dashboard.tsx`'s commented-out WebSocket toast hook).

### 9.2 Component Tree

```
App.tsx (TopBar + shell)
└── Dashboard.tsx (main 3-pane layout)
    ├── Left panel: Incident Queue (polled via GET /api/v2/incidents?state=open every 2s)
    ├── Center panel:
    │   ├── Situation Header Card (severity, status, lifecycle stepper, KPI tiles)
    │   ├── Consolidated Alerts (expandable list)
    │   ├── AgentConstellation.tsx (visual representation of agent activity, driven purely by incident.status — not truly wired to per-agent live state)
    │   ├── Root-Cause Hypotheses panel (evidence chips + causal-chain visualizer)
    │   ├── LiveOperationsConsole.tsx (SSE-driven audit event terminal)
    │   └── Business Impact panel (recharts Radar + affected-assets list)
    └── Right panel: Decision & Recovery
        ├── Recovery formulation checklist (derived from presence of hypothesis/evidence/plan)
        └── "View exact plan" / "Approve & Execute" buttons → PlanApprovalModal.tsx
```

### 9.3 Data Fetching Pattern

- **`useIncidentData(incidentId)`** (`hooks/useIncidentData.ts`) — a `setInterval`-based **polling** hook (every 2s) that fetches `evidence`, `hypotheses`, `plans`, `impact`, and `alerts` in parallel via `Promise.all`, with no caching layer (no TanStack Query, no dedupe). Polling stops automatically only when a plan reaches `APPROVED`/`EXECUTED` status.
- **`Dashboard.tsx`**'s `refreshQueue()` — a separate 2-second polling loop for the incident list itself (`GET /api/v2/incidents?state=open`).
- **`LiveOperationsConsole.tsx`** — the only component using real-time push (native browser `EventSource` against the SSE endpoint), with reconnect-on-error via `eventSource.onerror`.

This results in **three independent polling/streaming loops running concurrently per active incident view** (queue refresh, incident-detail data, and SSE), none of which are coordinated or backed off — acceptable for a demo, but not efficient at scale.

### 9.4 UI/Backend State Mismatches Worth Noting

- `LifecycleStepper` in `Dashboard.tsx` maps incident status strings to step indices using `.includes()` substring checks against a hardcoded list of 8 stages (`DETECTED`, `CORRELATED`, `INVESTIGATING`, `PLAN_READY`, `APPROVAL`, `EXECUTING`, `VERIFYING`, `RESOLVED`) — these do not exactly match the `IncidentState` enum values (e.g., `CORRELATED` vs `CORRELATING`, `APPROVAL` vs `AWAITING_APPROVAL`), relying on substring matching to paper over the difference.
- `PlanApprovalModal.tsx`'s `approvePlan()` sends `plan_hash: plan.action_plan_id` — i.e. it uses the plan's own ID as a fake "hash" rather than a real content hash of the plan, so the approval-binding/tamper-detection concept described in the roadmap (`plan_hash` as an integrity check) is not actually implemented; any value would be accepted since the backend doesn't validate the hash against plan content either.
- `Dashboard.tsx` computes "alerts to incident" ratios and job/product-impact counts using `evidence.length` as a proxy in the sidebar list (`{evidence.length + 2} alerts · ...`) rather than the actual `alerts` array length — a cosmetic approximation, not a real count.

---

## 10. Simulator (Scenario Lab) — Deep Dive

The `simulator_backend` service is a fully separate FastAPI app (port 8001) with its own `simulator-frontend` React control panel. It exists purely to make the system demoable without real production integrations wired up. Its two generation modes:

1. **Deterministic scenarios (`/trigger`)** — three named, hand-authored incident scenarios (`SCHEMA_REGRESSION`, `OOM_CRASH`, `CASCADING_FAILURE`) with realistic-looking logs and multi-source webhook payloads (Datadog, Airflow, PagerDuty, Sentry). `CASCADING_FAILURE` is the most elaborate: it seeds a 5-node dependency chain (`auth_db → auth_api → checkout_service → {payment_gateway, reporting_dashboard}`) and a matching runbook with an executable-looking SQL step (`pg_terminate_backend`), giving the RCA/Impact/Runbook agents real topology and runbook data to retrieve via their tools.
2. **AI-generated scenarios (`/trigger/ai`)** — takes a free-text prompt from the operator, asks Nemotron to invent an entire incident (logs, webhooks, business assets, runbooks) as structured JSON, persists it, and fires the webhooks. This is the "Scenario Lab" AI generation feature referenced in the enterprise roadmap and UI blueprint docs.

Both paths ultimately funnel into the same `/api/v2/ingest/webhook` endpoint used by any real external system, so from the API's perspective the simulator is indistinguishable from a genuine Datadog/Airflow/PagerDuty integration — a good architectural property (single ingestion surface) even though the current "connectors" (`airflow_connector.py`, `datadog_connector.py`) are unimplemented stubs.

---

## 11. Security Posture (Current State)

This section summarizes concrete, code-level security gaps observed, distinct from the target-state hardening plan in the roadmap document:

| Issue | Evidence | Risk |
|---|---|---|
| Hardcoded NVIDIA API keys | Present as fallback defaults in `orchestrator.py`, `base_agent.py`, and as a Compose env default in `docker-compose.yml` | Key leakage via source control / image layers |
| No authentication enforced on any live endpoint | `main.py` never applies `Depends(get_current_user)` despite `auth.py` being fully implemented | Any network-reachable client can read/mutate all incidents, approve plans, and trigger execution |
| Mock login issues tokens for any requested role with zero credential check | `GET /api/v2/auth/mock-login?role=admin` | Trivial privilege escalation if auth were later turned on without removing this endpoint |
| Fake `plan_hash` | `PlanApprovalModal.tsx` sends the plan ID as the "hash"; backend never verifies it | No real tamper-evidence/binding on approvals |
| SSE stream is unauthenticated and world-readable | `/events/stream` has no auth dependency | Audit trail (agent reasoning, evidence excerpts) is exposed to any caller |
| Arbitrary LLM-authored SQL example in seeded runbook | `simulator_backend/main.py` CASCADING_FAILURE seeds a runbook step containing a real `pg_terminate_backend` SQL statement | Demonstrates the exact "runbook step that could be dangerous if auto-executed" risk called out in the roadmap's threat model — currently harmless only because `execute_plan()` never actually runs step SQL |
| No tenant/workspace scoping enforced anywhere | Schema has `tenant_id`/`workspace_id`/`environment_id` columns (mostly defaulted, unused in queries) | Single-tenant only; not defense-in-depth ready |

---

## 12. Deployment & Environment

### 12.1 Docker Compose Topology

`docker-compose.yml` defines 6 services (see §1 table). Key details:
- `postgres`: standard `postgres:15-alpine`, health-checked via `pg_isready`; `api` and `temporal-worker` both `depends_on: postgres (service_healthy)`.
- `temporal`: uses `temporalio/admin-tools` image running `temporal server start-dev --ip 0.0.0.0` — i.e., **Temporal's dev-mode, single-process, in-memory-by-default server**, not a production Temporal cluster. This explains several of the durability gaps noted above (§7.1, §8.3) — a dev-mode Temporal server does not offer the same restart/HA guarantees the roadmap assumes for production Temporal.
- `api`: built from `Dockerfile.api`, exposes port 8000, connects to both `postgres` and `temporal` by service DNS name.
- `temporal-worker`: built from `Dockerfile.temporal`, separate container from `api` — correctly isolates the long-running agent/LLM workload from the request-handling API process, matching the roadmap's "investigation worker" separation principle.
- `frontend`: built via `Dockerfile.frontend` (multi-stage Vite build → nginx), served on port 80.
- `simulator`: built from `Dockerfile.simulator`, port 8001, connects to `postgres` and calls the `api` service by DNS name (`http://api:8000/...`).

### 12.2 Local Development Alternative

`start_app.command` and various root-level helper scripts (`add_env.py`, `clear_incidents.py`, `seed_cmdb.py`, `schema_check.py`, `migrate_code.py`, `update_*.py`) suggest an iterative, script-driven development history rather than a fully automated CI/CD pipeline — consistent with a hackathon-speed build-out. There is no CI configuration (GitHub Actions, etc.) visible for `pipeline-copilot/` itself, and no automated test suite covering the FastAPI endpoints or agent logic (only ad hoc scripts like `test_simulator.py`, `test_webhook.py`).

---

## 13. Summary of Architectural Gaps vs. Stated Design

This table consolidates the most consequential differences between what the documentation (`system_architecture.md`, `agent_architecture.md`, `nemoclaw_network_and_architecture.md`) describes and what the code actually does today:

| Documented behavior | Actual current behavior |
|---|---|
| "NemoClaw Agent Runtime" performs investigation | Native Python agents (`RCAAgent`, `DependencyAgent`, `RunbookAgent`, `GroundingCritic`) call NVIDIA NIM directly; `nemoclaw_repo/` is unused |
| Dependency Agent runs after RCA, using its finding | In the live LangGraph path, Dependency Agent runs in parallel with RCA using only a generic incident-ID string (sequential dependency only exists in the fallback path) |
| Safety/Verifier Agent independently validates the plan and can block execution | `GroundingCritic`'s `passed:false` result does not block anything — the plan is saved and surfaced regardless; independent verification checks (`verification_result`) are two hardcoded "PASSED" rows, not real checks |
| Human rejection triggers "dynamic runbook update" and re-tailored plan via the Agent Network | Rejection triggers a single raw LLM call patching the existing plan JSON; no agents are re-invoked |
| Approve & Execute leads to real (or at least workflow-durable) execution | Frontend calls `/approve`, which only signals a possibly-stale/absent Temporal workflow; execution logic itself unconditionally marks all steps "SUCCEEDED" without running anything |
| MCP-pattern tools registrable in sandboxed environments | Two disconnected implementations exist: `agent_tools.py` (direct function-calling, Postgres-backed, actually used) and `src/api/mcp_server.py` (real `fastmcp` server, SQLite-backed, unused) |
| "NemoClaw" branding implies use of the vendored NemoClaw sandbox/CLI project | `nemoclaw_repo/` is present in the tree but has no import references from any file under `src/`; it is a standalone OSS project vendored alongside, not integrated |
| Runbook Agent formulates recovery strategy from `runbooks.json`/DB runbooks specific to the incident | In the fallback path, the actual 4 recovery steps are hardcoded strings unrelated to the retrieved runbook content |
| State machine (`state_machine.py`) governs valid transitions | Never invoked; all state changes are raw SQL `UPDATE` statements |
| Deterministic `CorrelatorEngine.correlate()` clusters multiple alerts into one incident | Only `create_incident()` (single-alert path) is invoked; the clustering algorithm is unused in the live webhook flow |

---

## 14. Recommendations (Immediate, Low-Risk Fixes)

These are targeted fixes that would close the gap between documented and actual behavior without a large redesign (contrast with the long-term enterprise roadmap in `nemoguard_enterprise_productization_roadmap.md`):

1. **Fix the approve/execute flow gap (§8.3).** Either have `/approve` call `execute_plan()` directly when Temporal is unavailable/stale, or have the frontend call `/execute` after a successful `/approve`, so an incident is guaranteed to reach `RESOLVED` regardless of Temporal's live state.
2. **Enforce authentication** on at least the mutating endpoints (`/triage`, `/approve`, `/execute`, `/feedback`, `/ingest/webhook`) using the already-implemented `auth.py` dependencies.
3. **Remove or gate the mock-login endpoint** behind a `DEBUG`/`ENV=development` flag so it cannot be reached in any shared or production-like deployment.
4. **Reconcile severity string conventions** (`SEV_1` enum vs `SEV-1` string usage) across the simulator, orchestrator, and `/overview` SQL filters to avoid silently incorrect KPI counts.
5. **Wire the `state_machine.py` validator** into `orchestrator.py`'s state-changing calls to prevent invalid transitions as the system grows more paths.
6. **Make `execute_plan()` at least conditionally fail** based on plan content or a pluggable executor interface, rather than unconditionally marking all steps `SUCCEEDED` — even a "dry-run" simulated executor with per-step success/failure logic would materially improve trustworthiness of the demo.
7. **Either delete or clearly mark as deprecated** the unused legacy paths (`SQLite database.py`/`schema.sql`, `mcp_server.py`/`read_tools.py`, `CommanderAgent`/`_save_dynamic_triage()`, `ui/` Streamlit files) to reduce confusion for new contributors — currently ~30% of `src/` is dead code relative to the live request path.
8. **Real plan hashing.** Compute an actual content hash (e.g., SHA-256 over the normalized plan JSON) on the backend when a plan is created, return it to the frontend, and validate it server-side on `/approve` — turning the currently-decorative `plan_hash` field into a genuine tamper-check as intended by the domain model.

---

## 15. Conclusion

The current NemoGuard Pipeline Copilot implementation is a working, end-to-end demonstration of an agentic incident-response loop: **synthetic/real alert → LLM-driven correlation → parallel multi-agent investigation (RCA, Impact, Runbook, Grounding Critic) → structured recovery plan → human approval UI → simulated execution & verification → full audit trail surfaced via SSE.** It successfully proves the core product concept described in the pitch and roadmap documents using NVIDIA Nemotron models, LangGraph, Temporal, PostgreSQL, and a polished React dashboard.

The most important thing for any engineer picking up this codebase to understand is that **several documented behaviors (sequential agent dependency, safety-gate enforcement, real execution, deterministic multi-alert correlation, MCP tool governance) are either partially implemented, superseded by a simpler fallback, or entirely aspirational relative to the live code path** — this document exists specifically to make those gaps explicit and code-referenced so that the next phase of work (whether hackathon polish or the full enterprise productization roadmap) starts from an accurate baseline rather than the idealized description in the earlier docs.
