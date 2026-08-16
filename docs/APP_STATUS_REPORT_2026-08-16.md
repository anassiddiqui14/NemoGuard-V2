# NemoGuard Pipeline Copilot — Current Status & Design Report

**Generated:** 2026-08-16 · **Scope:** `pipeline-copilot/` (the actual running application; the vendored `nemoclaw_repo/` and the top-level hackathon docs/PDFs are excluded as reference material, not part of the running system)
**Purpose:** A single, accurate, up-to-date snapshot of what the app *is today* — architecture, features, what's real vs. simulated, and known gaps — as an input for you to build a prioritized improvement plan.

> This report reconciles several existing internal docs (`CURRENT_ARCHITECTURE_DESIGN_DOC.md`, `ENTERPRISE_BUILD_PROGRESS.md`, `IMPROVEMENT_PLAN.md`, `AGENT_CAPABILITIES_SNAPSHOT.md`, `LANDING_LOGIN_DASHBOARD_UPGRADE_PLAN.md`) against the **actual current code on disk**, including a large set of **uncommitted working-tree changes** (32 modified files + ~15 new files/directories relative to the single existing git commit) that post-date some of those docs. Where docs disagree with code, code wins.

---

## 1. Executive Summary

**NemoGuard Pipeline Copilot** is an agentic, AI-driven incident-response platform for data pipeline operations. It ingests alerts, correlates them into incidents, runs a multi-agent LLM investigation (root cause, impact, runbook retrieval, independent safety verification), produces a structured recovery plan, and — after human approval — executes and verifies remediation.

**Where it actually stands right now:**

- **Core agentic loop is real and working**: Watcher → RCA → (Impact + Runbook) → Grounding Critic → Human Approval → Execution → Verification, backed by NVIDIA Nemotron models, LangGraph, Temporal, and PostgreSQL.
- **A real (not purely simulated) execution path now exists** via a new **Capability Gateway** (`src/capabilities/`) — deterministic capability compilation, code-enforced policy, precondition checks, and independent verification — verified end-to-end against a **LocalStack-emulated AWS environment** (real S3/Lambda/CloudWatch/SQS/RDS/etc.), not just mocked DB rows. This is a major upgrade beyond the original hackathon prototype described in the architecture doc.
- **Security has been substantially hardened** since the original build: hardcoded API keys removed, auth enforced on mutating endpoints, real plan-hash integrity checking, approve→execute reliability fix. In the **uncommitted working tree**, a real credential-backed login system (`platform_user` table + `POST /api/v2/auth/login`) is being added alongside the original mock-login dev flow.
- **The frontend has grown substantially beyond a single dashboard**: real client-side routing (`react-router-dom`), a landing page, a login page, an app shell with nav rail, an "Intelligence" risk-overview page, incidents/agent-operations history views, settings, and a changelog — most of this is **new, currently uncommitted work**.
- **Known, mostly-documented gaps remain**: dev-mode (non-durable) Temporal server, no automated test suite / CI, several legacy/dead code paths not yet removed (~30% of `src/` by an earlier estimate), and an AWS tool asymmetry (rich read-only diagnostics, only 6 real write/action capabilities).

**Bottom line:** this is no longer a rough hackathon demo. It has a real governed action-execution substrate, real multi-hypothesis evidence modeling, and a genuinely verified integration test against real (LocalStack) infrastructure. But it is also mid-refactor: a large frontend redesign and a real-auth migration are sitting **uncommitted**, and structural gaps (dead code, no tests, dev-mode Temporal) still need addressing before this is production-ready.

---

## 2. System Architecture

### 2.1 Deployable Components (Docker Compose)

| Service | Tech | Role | Status |
|---|---|---|---|
| `postgres` | PostgreSQL 15 | Sole persistent store | ✅ Stable |
| `temporal` | Temporal dev-server | Durable workflow engine for the incident lifecycle | ⚠️ Dev-mode only (in-memory, not HA) |
| `api` | FastAPI (Python) | REST + SSE API, webhook ingestion, orchestration | ✅ Actively developed |
| `temporal-worker` | Temporal Python SDK worker | Executes `IncidentLifecycleWorkflow` | ✅ Stable |
| `frontend` | React 19 + Vite 8 + TS + Tailwind v4 | "NemoGuard Command Center" operator app | 🚧 Mid-redesign (uncommitted) |
| `simulator` | FastAPI (Python) | "Scenario Lab" — synthetic incident injection | ✅ Stable |
| `localstack` (opt-in, `--profile lab`) | LocalStack 3 | Real-AWS-API emulation (S3/Lambda/CloudWatch/SNS/SQS/IAM/Step Functions/Secrets Manager) | ✅ New, verified working |

### 2.2 High-Level Flow

```
Webhook / Simulator
   → WatcherAgent (classify real/noise, correlate to existing incident)
   → CorrelatorEngine (deterministic fingerprint/score — implemented but underused, see §6)
   → IncidentLifecycleWorkflow (Temporal)
       → triage_incident_activity → LangGraphInvestigator
             ├─ RCAAgent        (root cause, multi-hypothesis ledger)
             ├─ DependencyAgent (blast radius / CMDB)
             ├─ RunbookAgent    (recovery step retrieval)
             └─ GroundingCritic (independent, tool-using safety verifier)
       → [Human Approval Gate] (plan-hash verified, RBAC-gated)
       → execute_plan_activity → Capability Gateway
             (compile plan → policy check → precondition check → execute → independent verify)
   → Audit trail (SSE) → React dashboard
```

### 2.3 Repository Layout (actual, current)

```
pipeline-copilot/
├── src/
│   ├── api/            main.py (REST+SSE+auth), auth.py (JWT + new real login), mcp_server.py (legacy, unused)
│   ├── domain/
│   │   ├── agents/      base_agent, rca_agent, dependency_agent, runbook_agent,
│   │   │                watcher_agent, commander_agent (legacy), langgraph_investigator,
│   │   │                agent_tools.py (Postgres + LocalStack-lab tool functions)
│   │   ├── activities/  triage_activity.py, execution_activity.py (Temporal)
│   │   ├── workflows/   incident_workflow.py (IncidentLifecycleWorkflow)
│   │   ├── connectors/  airflow_connector.py, datadog_connector.py — unimplemented stubs
│   │   ├── tools/       aws_observability_tools.py (LocalStack-lab-only AWS diagnostics)
│   │   ├── correlator.py, evidence_authority.py, plan_hash.py, state_machine.py, enums.py, models.py
│   │   └── orchestrator.py   ← the central coordinator (44 graph edges per the knowledge graph)
│   ├── capabilities/    NEW governed execution substrate (models, registry, plan_compiler,
│   │                    policy, execution_engine, intent_mapper) — see §5
│   ├── tools/           legacy ToolRegistry/ReadTools/WriteTools — partially superseded by capabilities/
│   ├── store/           postgres_database.py (primary), database.py + schema.sql (legacy SQLite, unused)
│   ├── generator/       synthetic dataset/topology/log generation for the simulator
│   └── ui/              Streamlit-era UI — dead code, superseded by React frontend
├── migrations/          002 (domain model) → 007 (platform_user / real auth) — 6 migrations
├── config/              action_policy.yaml (legacy), capability_policy.yaml (new, admin-configurable)
├── localstack_lab/      NEW — real-infra break/remediate scenario scripts against LocalStack
├── frontend/            React app — see §7 for the (largely uncommitted) new structure
├── simulator_backend/   Scenario Lab FastAPI app
└── simulator-frontend/  Scenario Lab's own control-panel React app
```

---

## 3. Data Layer

- **Single source of truth:** PostgreSQL (`nemoguard_db`). Legacy SQLite code (`store/database.py`, `store/schema.sql`, `tools/read_tools.py`, `api/mcp_server.py`) remains in the repo but is **not used** at runtime — a removal/quarantine candidate.
- **Schema evolution via 6 migrations** (`002`–`007`): domain model → FK relaxation → Glue lab target table → **capability gateway** columns → **evidence authority** column → **`platform_user`** table (real auth, new).
- **Core tables:** `incident`, `incident_alert`, `evidence` (now carries `authority`: AUTHORITATIVE/HIGH/MEDIUM/LOW, code-computed), `hypothesis` (now a real multi-hypothesis ledger, ranked, with supporting/contradicting evidence — surfaced in the UI), `action_plan`/`action_step` (now capability-typed + hashed), `approval`, `action_execution` (now populated with real `verification_status`/`verification_details_json`), `audit_event` (SSE backbone), `agent_run`/`agent_step`/`tool_call` (partially used — designed for full observability, not fully populated), `platform_user` (new — real credential store).
- **Known lingering inconsistency:** `Severity` enum (`SEV_1`, underscore) vs. the string convention actually used everywhere else in code (`SEV-1`, hyphen) — silently affects dashboard KPI counts. Flagged in `IMPROVEMENT_PLAN.md` §2.5, not yet fixed per the current diff.
- **`state_machine.py`** (valid `IncidentState` transitions) is defined but **still not invoked** anywhere — all state changes are raw `UPDATE` statements.

---

## 4. Agentic Investigation Layer

| Agent | Model | Role | Tools |
|---|---|---|---|
| **WatcherAgent** | nemotron-3-super-120b | Classifies webhook validity, correlates to active incidents | None (pure LLM judgment) |
| **RCAAgent** | nemotron-3-ultra-550b | Root cause analysis — now returns a **ranked multi-hypothesis ledger** (≥2 competing hypotheses w/ confidence, supporting/contradicting evidence) instead of one flat finding | `query_logs`, `get_cmdb_context`, `get_runbook` + LocalStack-lab-only AWS tools (change intelligence via `list_recent_changes`) |
| **DependencyAgent** | nemotron-3-super-120b | Downstream blast-radius via CMDB | `get_cmdb_context` |
| **RunbookAgent** | nemotron-3-super-120b | Retrieves/matches SOPs, proposes recovery steps | `get_runbook` + LocalStack-lab tools |
| **GroundingCritic** ("Safety Agent") | nemotron-3-ultra-550b | Final independent safety gate. Now uses `call_llm_with_tools` (previously zero tool access) against a **read-only-only tool schema** — structurally cannot call any write/action tool, so it can verify but never act | 19 read-only diagnostic tools (Postgres + LocalStack-lab AWS) |
| **CommanderAgent** | nemotron-3-ultra-550b | Legacy single-shot synthesizer, superseded by the LangGraph flow; still used by the sequential fallback path and the feedback/revision path | none |

**Orchestration:** LangGraph `StateGraph` runs RCA + Impact + Runbook, then Grounding Critic synthesizes. A fallback sequential path (`triage_fallback`) runs if LangGraph throws.

**Structural (code-enforced, not just prompted) safety control confirmed in code:** `_plan_violates_data_integrity_policy()` in `langgraph_investigator.py` inspects the *actual* returned plan steps and forces `passed: false` if a write-job rerun is proposed without a preceding staleness check — one concrete example of policy enforced in code rather than trusted from the LLM.

**Still-open gaps in this layer** (per the architecture doc, largely still valid against current code):
- In the live LangGraph path, the Impact/Runbook nodes still run in parallel with RCA using a generic incident-ID string, not the RCA finding — sequential dependency only exists in the fallback path (`IMPROVEMENT_PLAN.md` §2.1, not yet implemented).
- The fallback path's recovery steps are 4 hardcoded generic strings, not derived from the actual incident (§2.2, not yet fixed).
- Feedback/rejection re-planning (`triage_feedback()`) still patches the existing plan text with one LLM call rather than re-running the full multi-agent investigation (§2.6, not yet fixed).
- `CorrelatorEngine.correlate()` (deterministic multi-alert clustering) remains implemented but unused in the live webhook path; correlation is still 100% delegated to the WatcherAgent's LLM judgment (§2.7, not yet fixed).

---

## 5. Capability Gateway — Real Execution Substrate (New Since the Architecture Doc)

This is the single largest functional upgrade beyond what `CURRENT_ARCHITECTURE_DESIGN_DOC.md` describes. Previously, `execute_plan()` unconditionally marked every step "SUCCEEDED" and inserted two hardcoded "PASSED" verification rows — pure theater. That has been replaced.

**Built (`src/capabilities/`):**
- `models.py` — typed Pydantic contracts: `ActionIntent`, `CompiledAction`, `CompiledPlan`, `ActionResult`, `VerificationOutcome`, `CapabilityDefinition`.
- `registry.py` — catalog of **6 real capabilities**, each with separate `precondition_check`/`execute`/`verify` callables:
  - `data.check_table_staleness` (READ_ONLY, AUTOMATIC)
  - `data.cleanup_partial_write` (MEDIUM, HUMAN_APPROVAL_REQUIRED, dry-run-first)
  - `data.idempotent_rerun_order_events_job` (MEDIUM, HUMAN_APPROVAL_REQUIRED)
  - `compute.rerun_ingest_job` (MEDIUM, HUMAN_APPROVAL_REQUIRED)
  - `ops.verify_row_count_matches_expected` (READ_ONLY, AUTOMATIC)
  - `ops.manual_step` (fallback for unmapped actions — always `INCONCLUSIVE`, never self-verifies)
- `plan_compiler.py` — deterministic `ActionIntent → CompiledAction` resolution + SHA-256 plan hashing. No LLM output is trusted to name a capability directly.
- `policy.py` — deterministic risk/autonomy → approval-requirement mapping in **code**, with an admin-configurable YAML override (`config/capability_policy.yaml`) that can only make policy stricter, never looser than the code default (fail-safe on typos/unknown IDs).
- `execution_engine.py` — the generic precondition-check → execute → **independent**-verify engine, including a **Step-0 policy re-check at execution time** (not just at approval time), closing a gap where policy could be bypassed by a later direct call.
- `intent_mapper.py` — compatibility bridge letting existing free-text `action_step.tool_name` strings from agent prompts flow through the new pipeline without requiring every prompt to emit structured JSON immediately.

**Wired into `orchestrator.py::execute_plan()`** — replaced the old hardcoded unconditional-success logic with a real per-action loop; the incident is only marked `RESOLVED` if every action's independent verification actually passed, otherwise `FAILED` + an `INCIDENT_ESCALATED` audit event.

**Verified end-to-end against real infrastructure (not mocked):** a genuine partial-write crash was triggered in the LocalStack lab (`break_order_events_scenario.py`), and the full compile → policy-evaluate → execute → verify pipeline was run through the actual production code path (`IncidentOrchestrator.execute_plan`), confirming real `action_step.status`, `capability_id`, `verification_status = PASSED`, and `incident.status = RESOLVED` derived from genuine independent verification — not a hardcoded assumption.

**Admin API for the capability catalog** (`GET /api/v2/admin/capabilities`, `POST /api/v2/admin/capabilities/reload-policy`) — admin-only (RBAC-enforced, confirmed via live test that a `viewer` token is rejected with 403), runs the exact same policy function the runtime execution engine uses (no display-only logic divergence risk).

**Still limited:** only 6 capabilities exist; the AWS diagnostic tool surface (19 read-only tools) is much richer than the action surface (essentially 1 real Postgres write action + 2 rerun paths). No generic `{tool_name, args}` execution engine exists for arbitrary AWS services (ECS restart, Step Function retry, DLQ redrive, ASG scale, RDS reboot, secret rotation, etc. are all diagnosis-only today). See `AGENT_CAPABILITIES_SNAPSHOT.md` §5 for the full gap list.

---

## 6. Orchestration & Workflow Layer

- **Temporal** drives `IncidentLifecycleWorkflow`: triage activity → durable wait for human approval signal → execute activity. Runs on **dev-mode Temporal** (single-process, in-memory) — not production-durable; a worker/API restart during an open incident can orphan workflow state. No signal path exists yet for "revise plan" — feedback goes through a synchronous side-channel API call, not through the workflow.
- **Approve → Execute reliability fix (done):** `POST /plans/{id}/approve` now falls back to direct `execute_plan()` if Temporal is unreachable or the workflow handle is stale — closing the previously-documented "incident stuck in APPROVED forever" bug.
- **Plan-hash integrity (done):** `src/domain/plan_hash.py` computes a real SHA-256 hash over plan-relevant fields; `/approve` validates the submitted hash against a freshly recomputed one and returns `409 Conflict` on mismatch (e.g., plan was revised since fetched).

---

## 7. API Layer (FastAPI) — Current Endpoint & Auth State

**Authentication — significantly more complete than the architecture doc describes:**
- Legacy: `GET /api/v2/auth/mock-login?role=...` — now gated behind `ENV=development`/`dev`/`local` (was previously wide open).
- **New (uncommitted):** `POST /api/v2/auth/login` — real email/password login against the new `platform_user` table (hashed passwords, `verify_password()`), issuing a JWT with the user's real roles/tenant/workspace. `GET /api/v2/auth/config` exposes whether credential login is available (i.e., whether any active `platform_user` row exists) so the frontend can decide whether to show a real login form or fall back to the demo mock-login.
- `Depends(get_current_user)` now applied to `/triage`, `/agent-findings`, `/feedback`, `/plans/{id}/approve`. `Depends(require_role("commander"))` on `/plans/{id}/execute`. `Depends(require_role("admin"))` on the two admin capability endpoints.
- **Still open (unauthenticated):** all `GET /api/v2/incidents*`, `/alerts*`, `/context/*` read endpoints, and the SSE `/events/stream` endpoint — acceptable for a single-operator demo, explicitly flagged as needing lockdown before any multi-user/external deployment.

**Endpoint inventory (unchanged in shape from the architecture doc, plus the new auth endpoints above):** status/overview, incident reads (list/detail/summary/hypotheses/evidence/impact/plans/events/alerts), agent/LLM context endpoints (`/context/*` — legacy integration surface, unused by native agents), webhook ingestion, triage/approve/execute/feedback, admin capability endpoints, SSE stream.

**Known remaining nuance:** the frontend's execute flow historically called `/approve` (not `/execute`) — now resolved by the approve→execute fallback in §6, but worth confirming the frontend's actual call sequence still matches given the ongoing frontend rewrite.

---

## 8. Frontend — Major In-Progress Redesign (Mostly Uncommitted)

The frontend has grown substantially beyond the single-dashboard app the architecture doc describes. Per `git status`, **most of this is new/uncommitted work**:

### 8.1 Stack additions
`react-router-dom` (routing, newly added), `@react-three/fiber` + `@react-three/drei` + `three` (3D landing-page hero, newly added) — React 19, Vite 8, TypeScript 6, Tailwind v4 (already present).

### 8.2 New route tree (`src/app/routes.tsx`)
```
/                      → LandingPage (public, 3D scroll hero)
/login                 → LoginPage (public)
/app  (RequireAuth)    → AppShell
  /app                    → Dashboard (Command Center) [index]
  /app/incidents          → IncidentsPage
  /app/agent-operations   → AgentOperationsPage
  /app/intelligence       → IntelligencePage (NEW — manager-level risk overview, stat cards + risk-ranked queue)
  /app/whats-new          → WhatsNewPage
  /app/settings           → SettingsPage
```
Legacy `App.tsx`/`App.css` are deleted; replaced by `AppShell.tsx` + `UserMenu.tsx` + `GreetingBar.tsx` + `GlobalNavRail.tsx`. Note: `routes.tsx` currently defines `/app/intelligence` and `/app/whats-new` — the original upgrade plan doc did not finalize an "Intelligence" page name (it planned "Agent Operations"/"Settings"/"What's New" only), so this is a genuinely new page added during implementation, beyond the original design doc.

### 8.3 New pages/components (uncommitted)
- **`LandingPage`** — scroll-driven marketing/product page with a 3D `AgentConstellation3D` hero (React Three Fiber), `LifecycleShowcase`, `EvidenceShowcase`, `MetricsStrip`, `FeatureGrid`, `CtaBand`.
- **`LoginPage`** — split layout, demo role selector, calls the mock-login or (new) real credential login depending on `GET /api/v2/auth/config`.
- **`AuthGateContext`** — "Demo Mode" toggle (skip login) persisted to `localStorage`, per the design doc §3.2 Option C.
- **`IntelligencePage`** (new) — stat cards (active incidents, critical/SEV-1 risk, review-required, resolved-today) + a risk-ranked incident list. Polls `/api/v2/incidents` every 5s. Explicitly designed as a manager/on-call-lead-level summary distinct from the per-incident Command Center.
- **`IncidentsPage`, `AgentOperationsPage`, `SettingsPage`, `WhatsNewPage`** — nav-rail-accessible pages filling out the IA described in the upgrade plan; `WhatsNewPage` (a full page) exists instead of the originally-planned slide-in panel, and there is no separate `WhatsNewPanel` slide-in component per the file listing — the design apparently evolved during implementation.
- **`useCurrentUser`, `useGreeting`** — new hooks for JWT-decoded display name and time-of-day greeting text, feeding `GreetingBar`.
- **`data/changelog.ts`** — static versioned changelog array feeding `WhatsNewPage`.

### 8.4 Dashboard (Command Center) itself
Already substantially reworked from the original monolithic 700-line component (per `ENTERPRISE_BUILD_PROGRESS.md` Phase 3.7 / Phase 6) into `IncidentQueue`, `SituationHeader`, `InvestigationPanels`, `RecoveryRail`, `EvidenceModal`, `shared.tsx` (formatters/badges/`LifecycleStepper`/`EmptyState`), plus newer `IncidentWorkspace.tsx` and `WorkspaceTabs.tsx` (new, uncommitted) — suggesting the tabbed Overview/Evidence/Impact/Activity reorganization described in `LANDING_LOGIN_DASHBOARD_UPGRADE_PLAN.md` §4.2.1 has begun implementation.

### 8.5 Verified working (per docs)
- `AgentConstellation.tsx` rewritten to derive live per-agent state from real SSE audit events (matched by actor + event type) rather than a single coarse `incident.status` string — confirmed live: cards visibly transition QUEUED→RUNNING as real backend events stream in.
- `useIncidentEvents.ts` — single shared SSE subscription per incident, used by both the constellation and the live console so they stay in sync (previously two independent, desynced sources).
- Hypothesis ledger + evidence-authority badges now actually rendered in `EvidenceModal` (previously silently discarded a real bug: only `hypData[0]` was kept, throwing away every alternative hypothesis the RCA agent produced).
- `npm run build` (`tsc -b && vite build`) reported passing cleanly as of the last documented verification pass.

### 8.6 Risk of this section
Because so much of §8 is **uncommitted**, there is real risk of losing this work (no commit checkpoint) and of the app being in a partially-integrated state right now (e.g., new pages wired into routing but not yet visually/functionally polished, per the upgrade plan's own "remaining polish" list). This should be the **first item** in any improvement plan: commit/checkpoint this work before doing anything else.

---

## 9. Simulator (Scenario Lab)

Unchanged in shape from the architecture doc: a separate FastAPI service (port 8001) with `/trigger` (3 deterministic scenarios: `SCHEMA_REGRESSION`, `OOM_CRASH`, `CASCADING_FAILURE`) and `/trigger/ai` (free-text-prompt AI-generated synthetic incidents via Nemotron). Both funnel into the same `/api/v2/ingest/webhook` used by real integrations — a good architectural property. `airflow_connector.py`/`datadog_connector.py` remain unimplemented stubs.

**New addition: `localstack_lab/`** — a parallel "real infrastructure" scenario mechanism (`break_order_events_scenario.py`, `break_pipeline_scenario.py`, `break_notification_scenario.py`, `provision.py`, `remediate.py`, `forwarder.py`) that actually breaks real (LocalStack-emulated) AWS resources rather than only writing synthetic DB rows — this is what the Capability Gateway (§5) was verified against. Opt-in via `docker compose --profile lab up -d`.

---

## 10. Security Posture — Current State

| Area | Status |
|---|---|
| Hardcoded NVIDIA API keys | ✅ Removed; env vars now required, fail-fast if missing (`docker-compose.yml` uses `${VAR:?error}` syntax) |
| Auth on mutating endpoints | ✅ Done for triage/agent-findings/feedback/approve/execute/admin; ❌ still open for all GET reads + SSE stream |
| Mock-login exposure | ✅ Gated behind `ENV=development` |
| Real credential login | 🚧 In progress (uncommitted) — `platform_user` table + `/auth/login` exist; migration to fully replace mock-login as the primary path is not yet complete/committed |
| Plan-hash integrity | ✅ Real SHA-256 hash, validated server-side on approve, `409` on mismatch |
| Approve→Execute reliability | ✅ Fixed via fallback to direct execution |
| State-machine enforcement | ❌ Still not wired in; all transitions are raw SQL updates |
| Severity string convention | ❌ Still inconsistent (`SEV_1` enum vs `SEV-1` usage) |
| Rate limiting | ❌ Not implemented (webhook + `/trigger/ai` both unlimited) |
| Input validation on webhook payloads | ❌ Arbitrary JSON, no size cap |
| Secrets scanning in CI | ❌ No CI exists at all |
| CORS | ⚠️ Simulator uses `allow_origins=["*"]`; fine for local demo only |
| Tenant/workspace scoping | ❌ Columns exist, not enforced in any query |

---

## 11. Testing & CI

**No automated test suite and no CI pipeline exist.** Only ad hoc manual scripts: `test_simulator.py`, `scripts/test_webhook.py`. `IMPROVEMENT_PLAN.md` §4.5 proposes a minimal suite (plan-hash unit tests, correlator unit tests, auth integration tests, an end-to-end webhook-flow test with `testcontainers`) — none of this exists yet in the codebase. This is one of the most significant gaps for any path toward production-readiness, since a large amount of security- and correctness-critical logic (plan hashing, policy enforcement, correlation scoring, state transitions) currently has zero regression protection.

---

## 12. Known Dead / Legacy Code (Candidates for Removal or Quarantine)

- `src/store/database.py` + `src/store/schema.sql` (legacy SQLite, superseded by Postgres)
- `src/tools/read_tools.py` + `src/api/mcp_server.py` (real `fastmcp` server, SQLite-backed, entirely disconnected from the live agents)
- `src/domain/agents/commander_agent.py` + `_save_dynamic_triage()` (superseded by LangGraph, but still used by the feedback/fallback paths — so not fully dead, just partially)
- `src/ui/` — Streamlit-era UI (`alert_streamer.py`, `app.py`, `incident_commander.py`), fully superseded by the React frontend
- `src/tools/registry.py` (`ToolRegistry`) — actually a *better* pattern (real risk/approval policy enforcement) than the live `agent_tools.py` direct-call approach, but currently unused by any live agent; `IMPROVEMENT_PLAN.md` recommends migrating *toward* it, not deleting it
- `nemoclaw_repo/` at the top level — a large vendored NVIDIA OSS project with zero import references from `src/`; present as branding/reference inspiration only, not integrated

Estimated at ~30% of `src/` being unused relative to the live request path (per the architecture doc's own estimate) — likely still roughly accurate given no removal work has landed since.

---

## 13. Summary Table — Documented Design Intent vs. Actual Current Behavior

| Area | Originally documented / intended | Actual current state |
|---|---|---|
| Agent execution engine | NemoClaw Agent Network runtime | Native Python agents call NVIDIA NIM directly; `nemoclaw_repo/` unused |
| Plan execution | Real/durable execution | **Now real** for 6 registered capabilities via the Capability Gateway, verified against LocalStack; still simulated/manual (`ops.manual_step`) for anything unmapped |
| Safety gate | Independently validates and can block execution | Critic's `passed:false` now sets a distinct `NEEDS_REVIEW` status with a UI-visible banner + explicit acknowledgement gate (per `ENTERPRISE_BUILD_PROGRESS.md` Phase 6) — a real improvement over the earlier "cosmetic" gate |
| Correlation | Deterministic multi-alert clustering | Still LLM (Watcher) driven for real correlation; `CorrelatorEngine.correlate()` unused |
| Auth | Full JWT + RBAC | Enforced on mutations; reads/SSE still open; real credential login in progress |
| Frontend | Single dense dashboard | Multi-page app with routing, landing/login, nav rail, Intelligence page — much of this uncommitted |
| Tooling for AWS ops | — | Rich read-only diagnostics (19 tools) vs. narrow real write capability (6, mostly Postgres/Lambda-rerun) |
| Testing | — | None exists |

---

## 14. Suggested Next Steps (for your improvement plan — not yet prioritized/ordered)

This report intentionally stops short of prescribing priorities (per your ask to review first), but the most consequential open items to weigh are:

1. **Commit the uncommitted working tree** (frontend redesign + real-auth migration) before any further work — real risk of loss otherwise.
2. **Decide the fate of the real-auth migration** — finish wiring `platform_user`/`/auth/login` as the primary path (with mock-login demoted to a clearly-labelled dev fallback), or explicitly defer it; right now it's half-in.
3. **Close the functional-correctness gaps in §4** (sequential Impact/Runbook after RCA, non-hardcoded fallback steps, feedback re-invoking full investigation, deterministic correlator as first-pass filter) — these directly affect how credible the AI investigation is in any demo or real use.
4. **Stand up a minimal automated test suite + CI** (§11) — currently the highest-leverage risk-reduction investment given zero existing coverage over security- and correctness-critical logic.
5. **Expand the Capability Gateway's action surface** (§5) if the goal is genuine autonomous remediation beyond the current 6 capabilities — likely the single biggest lever for making the "AI SRE" pitch real rather than aspirational.
6. **Address the remaining security backlog** (§10): read-endpoint auth, tenant scoping, rate limiting, webhook input validation, SSE auth, secrets scanning.
7. **Clean up dead code** (§12) or at minimum document it as legacy/quarantined, to reduce onboarding confusion for anyone else touching this codebase.
8. **Move Temporal off dev-mode** if any deployment needs to survive restarts with in-flight incidents.

---

## 15. Sources Consulted

- `pipeline-copilot/README.md`
- `pipeline-copilot/docs/CURRENT_ARCHITECTURE_DESIGN_DOC.md`
- `pipeline-copilot/docs/ENTERPRISE_BUILD_PROGRESS.md`
- `pipeline-copilot/docs/IMPROVEMENT_PLAN.md`
- `pipeline-copilot/docs/AGENT_CAPABILITIES_SNAPSHOT.md`
- `pipeline-copilot/docs/LANDING_LOGIN_DASHBOARD_UPGRADE_PLAN.md`
- Live inspection: `git log`/`git status`/`git diff --stat`, `src/` and `frontend/src/` directory trees, `migrations/007_platform_users.sql`, `frontend/package.json`, `pyproject.toml`, `docker-compose.yml`, `config/capability_policy.yaml`, `config/action_policy.yaml`, `frontend/src/app/routes.tsx`, `frontend/src/pages/IntelligencePage/IntelligencePage.tsx`, `src/api/main.py` auth-related grep, `src/domain/agents/langgraph_investigator.py` diff, the project's Graphify knowledge graph (`IncidentOrchestrator` node explanation).
