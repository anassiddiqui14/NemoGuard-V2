# NemoGuard Pipeline Copilot — Comprehensive Improvement Plan

**Purpose:** A concrete, prioritized plan to evolve this project from a hackathon prototype into a credible, secure, production-shaped application — covering security remediation (including the NVIDIA API key rotation you just triggered by deleting your keys), visual/UX polish, and functional/architectural hardening.

**How to use this document:** Work top-to-bottom. Phase 0 is required before you can even run the app again (new keys). Phases 1–2 are security-critical and should be done before showing this to anyone outside your own machine. Phases 3–5 are the functional and visual improvements that turn "demo" into "product."

Cross-reference: `docs/CURRENT_ARCHITECTURE_DESIGN_DOC.md` §11 (Security Posture) and §13 (Architectural Gaps) documents every issue addressed below with exact file/line context.

---

## Phase 0 — Get Running Again (New NVIDIA Key)

You deleted your NVIDIA keys, and I've already removed every hardcoded fallback key from the codebase (see "Security remediation already applied" below). The app **will not start** until you provide a new key via environment variables — this is now enforced by design, not an accident.

### Steps

1. **Get a new NVIDIA API key**
   Go to https://build.nvidia.com/ → sign in → API Keys → generate a new key (starts with `nvapi-`).

2. **Create your local `.env` file**
   ```bash
   cd pipeline-copilot
   cp .env.example .env
   ```

3. **Edit `.env` and fill in real values:**
   ```
   NVIDIA_API_KEY=nvapi-<your-new-key>
   JWT_SECRET=<run: python3 -c "import secrets; print(secrets.token_urlsafe(48))">
   ENV=development
   ```

4. **Docker Compose will now read `.env` automatically** (Compose auto-loads a `.env` file in the same directory as `docker-compose.yml`). Start the stack:
   ```bash
   docker compose up --build
   ```
   The `api`, `temporal-worker`, and `simulator` services will now **fail fast with a clear error** if `NVIDIA_API_KEY` or `JWT_SECRET` are missing (previously they'd silently fall back to a hardcoded/leaked key — this fail-fast behavior is intentional and is the correct production posture).

### Security remediation already applied (done for you)

| File | Change |
|---|---|
| `src/domain/orchestrator.py` | Removed hardcoded `NVIDIA_API_KEY` fallback; now warns and requires env var |
| `src/domain/agents/base_agent.py` | Removed hardcoded fallback key; warns per-agent if missing |
| `simulator_backend/main.py` | Removed `"nvapi-dummy"` fallback; the `/trigger/ai` endpoint now returns a clear error if the key is missing instead of silently failing against NVIDIA's API |
| `docker-compose.yml` | `NVIDIA_API_KEY` and `JWT_SECRET` are now **required** (`${VAR:?error message}` syntax) — Compose refuses to start a service if they're unset, rather than injecting a leaked default |
| `src/api/auth.py` | `JWT_SECRET` no longer has an insecure hardcoded default (`"super-secret-development-key"`); app raises `RuntimeError` on import if unset |
| `.env.example` | New file documenting every required/optional environment variable |
| `.gitignore` | Already correctly ignores `.env` (confirmed, no change needed) |

**Action item for you:** search your git history for the leaked keys and consider them permanently compromised (you already deleted them from NVIDIA, which is the right move). If this repo was ever pushed to a remote (GitHub/GitLab), those keys are in the git history forever unless you rewrite history (`git filter-repo` / BFG) — not required since you've revoked them, but good practice.

---

## Phase 1 — Security Hardening (Critical, Do Before Any External Demo)

These close the remaining gaps identified in the architecture doc §11 that go beyond the key issue.

### 1.1 Authentication enforcement — ✅ partially done, needs completion

**Done:**
- `/triage`, `/agent-findings`, `/feedback`, `/plans/{id}/approve` now require `Depends(get_current_user)`.
- `/plans/{id}/execute` now requires the `commander` role via `Depends(require_role("commander"))`.
- `/auth/mock-login` now 404s unless `ENV=development`.

**Remaining work:**
- [ ] Add `Depends(get_current_user)` to all `GET /api/v2/incidents*`, `/alerts*`, `/context/*` endpoints — currently these remain open reads. For a single-operator demo this is acceptable short-term, but before any multi-user or externally-reachable deployment, lock these down too.
- [ ] Add tenant-scoping: every query in `main.py` currently has no `WHERE tenant_id = ...` clause. Add a `tenant_id` column check using `current_user.tenant_id` once you have more than one logical tenant/environment.
- [ ] Replace `localStorage` token storage in the frontend with an httpOnly cookie once you have a real backend session/login flow (localStorage is vulnerable to XSS token theft). Acceptable for now given the mock-login dev flow.
- [ ] Build a real login screen (see Phase 4 UX) instead of silently auto-fetching a mock commander token — right now `App.tsx`'s `useAuthToken()` will silently grant "commander" permissions to anyone who loads the page while `ENV=development`. This is fine for solo development, but you must gate this behind `ENV=development` (already done) and build a real login UI before `ENV=production`.

### 1.2 Plan-hash integrity — ✅ done

- Added `src/domain/plan_hash.py` — computes a real SHA-256 hash over the plan's approval-relevant fields (rationale, risk, steps, parameters).
- `GET /incidents/{id}/plans` now returns the real `plan_hash` per plan.
- `POST /plans/{id}/approve` now **validates** the submitted hash against a freshly recomputed one and returns `409 Conflict` if the plan changed since it was fetched (e.g., revised via feedback) — closing the "approve a plan you didn't actually see" gap.
- Frontend (`PlanApprovalModal.tsx`, `Dashboard.tsx`) updated to send the real hash instead of `plan.action_plan_id` / `"ui-approved"`.

### 1.3 Approve → Execute reliability gap — ✅ done

- `POST /plans/{id}/approve` now attempts the Temporal signal, but **falls back to direct execution** (`orchestrator.execute_plan()`) if Temporal is unreachable or the workflow handle is stale/absent. This closes the "incident stuck in APPROVED forever" bug documented in the architecture doc §8.3.

### 1.4 Remaining hardening backlog

- [ ] **Rate limiting.** Add `slowapi` or a reverse-proxy rate limit (nginx `limit_req`) in front of `/ingest/webhook` and `/trigger/ai` — both currently accept unlimited unauthenticated requests and both can trigger expensive LLM calls (cost/DoS risk).
- [ ] **Input validation on webhook payloads.** `ingest_webhook(payload: dict)` accepts arbitrary JSON with no size limit or schema validation before handing it to the LLM (`WatcherAgent`). Add a Pydantic model with `max_length` constraints on string fields and a total payload size cap (e.g. 64KB) at the FastAPI layer.
- [ ] **Secrets scanning in CI.** Add `gitleaks` or `trufflehog` as a pre-commit hook and CI gate so a hardcoded key like the ones just removed can never be merged again.
- [ ] **SSE endpoint auth.** `/incidents/{id}/events/stream` remains unauthenticated — add a token query-param check (EventSource can't send custom headers) validated against `get_current_user`'s JWT logic.
- [ ] **CORS.** Frontend and API currently rely on same-origin/nginx proxying in Docker Compose; if you ever split domains, add an explicit `CORSMiddleware` allowlist rather than `allow_origins=["*"]` (currently only the simulator has `allow_origins=["*"]`, which is fine for a local demo tool but should be tightened if exposed).
- [ ] **State-machine enforcement.** Wire `src/domain/state_machine.py` into every `UPDATE incident SET status = ...` call site so invalid transitions (e.g. `RESOLVED → INVESTIGATING` without going through `ROLLED_BACK`) are rejected rather than silently applied.

---

## Phase 2 — Functional Correctness (Make the Demo Trustworthy)

These fix behaviors that currently make the AI investigation less credible than it looks.

### 2.1 Fix the LangGraph parallel Dependency Agent gap
**Problem:** In `langgraph_investigator.py`, the `impact` node calls `DependencyAgent.analyze(f"Investigating incident {incident_id}")` — a generic string, not the actual RCA finding — because it runs in parallel with the RCA node.
**Fix:** Restructure the graph so `impact` and `runbook` depend on `rca` completing first (sequential edges: `rca → impact`, `rca → runbook`), passing `state["rca_result"]["finding"]` into the Dependency Agent's prompt. This costs some latency but produces meaningfully better, evidence-grounded impact analysis — directly improving the "Business Impact" panel's accuracy.

### 2.2 Replace the hardcoded fallback recovery steps
**Problem:** `orchestrator.triage_fallback()` always inserts the same 4 hardcoded steps ("Rollback schema mapping to v118...") regardless of the actual incident.
**Fix:** Either (a) remove the fallback's canned steps and instead ask the LLM (via `RunbookAgent` or a direct `call_llm_json`) to generate steps grounded in the RCA finding + retrieved runbook, or (b) if keeping a deterministic fallback for reliability, make the steps template-driven from `runbook_step` rows matched by `cause_type`, not hardcoded prose.

### 2.3 Make the Grounding Critic's `passed: false` actually matter
**Problem:** If `GroundingCritic` returns `passed: false`, the plan is still saved as `PENDING_APPROVAL` — the safety gate is cosmetic.
**Fix:** When `critic_passed` is `False`, set `action_plan.status = 'NEEDS_REVIEW'` (new status) instead of `PENDING_APPROVAL`, and surface a visible warning banner in `PlanApprovalModal.tsx` ("⚠ Safety Agent flagged this plan: {critic_feedback}") that the operator must explicitly acknowledge before the Approve button is enabled.

### 2.4 Real verification instead of hardcoded PASSED checks
**Problem:** `execute_plan()` always inserts two hardcoded `verification_result` rows marked "PASSED" regardless of what the plan actually did, and unconditionally marks every `action_step` as `SUCCEEDED` without running anything.
**Fix (incremental):**
1. Start with **one real, safe, read-only verification check** per incident type — e.g. for `SCHEMA_REGRESSION`, actually re-query `log_event` for the same `error_code` after "execution" and confirm no new occurrences in the last N minutes. This is deterministic, cheap, and turns at least one check from theater into substance.
2. Model `action_execution` rows properly (currently unused) so each step's simulated outcome is individually recorded with a timestamp, not just a blanket `UPDATE ... SET status = 'SUCCEEDED'`.
3. Introduce a pluggable `Executor` interface (`src/domain/executors/base.py`) with a `SimulatedExecutor` (current behavior, but step-by-step with realistic delays and a random small chance of simulated failure for demo realism) and a future `RealExecutor` per tool (see Phase 4.3).

### 2.5 Fix severity string convention mismatch
**Problem:** `Severity` enum uses `SEV_1`/`SEV_2` (underscore), but the simulator and `/overview` SQL filters use `SEV-1`/`SEV-2` (hyphen) — a silent bug that can make dashboard KPI counts wrong.
**Fix:** Standardize on one convention (recommend hyphenated `SEV-1..4` since that's what's actually used everywhere except the enum definition), update `src/domain/enums.py::Severity` to match, and add a unit test asserting `Severity.SEV_1.value == "SEV-1"` (rename the enum member values, not the Python identifiers) so this can't silently regress.

### 2.6 Re-run investigation on feedback rejection instead of patching text
**Problem:** `triage_feedback()` only asks the LLM to patch the existing plan's rationale/steps in a single call — it doesn't re-run RCA/Impact/Runbook agents, so a rejection like "your root cause is wrong" can't actually change the diagnosis, only the wording of the plan.
**Fix:** When feedback indicates disagreement with the root cause (detectable via a quick classification call, or simply always), re-invoke `LangGraphInvestigator.investigate()` with the feedback text injected into the RCA agent's prompt as additional context ("A human reviewer rejected the previous finding for this reason: {feedback}. Reconsider the evidence."), then run `save_agent_findings()` again to produce a genuinely revised diagnosis + plan, not just a reworded one.

### 2.7 Use the deterministic CorrelatorEngine for its intended purpose
**Problem:** `CorrelatorEngine.correlate()` (multi-alert clustering with topology/time/error-signature scoring) is fully implemented but never called — real correlation is 100% delegated to the WatcherAgent's LLM judgment.
**Fix:** Run `CorrelatorEngine.correlate()` as a **first-pass deterministic filter** before the WatcherAgent call: if the deterministic score against an existing incident is already ≥ `min_cluster_score`, skip the LLM call entirely (correlate immediately, cheaper and more predictable). Only fall through to the LLM-based `WatcherAgent` classification when the deterministic engine is ambiguous (score between e.g. 0.3–0.6) or when creating a brand-new incident. This is both a cost optimization (fewer LLM calls) and a correctness improvement (deterministic ground truth takes precedence over probabilistic LLM judgment, matching the design principle in the enterprise roadmap: *"Deterministic truth, probabilistic advice"*).

---

## Phase 3 — Visual / UX Improvements

The current dashboard (`Dashboard.tsx`) is already a strong "enterprise SaaS" visual foundation (dark command-center aesthetic, Framer Motion, Recharts). These changes elevate it further without a rewrite.

### 3.1 Fix visual/state inconsistencies (quick wins)
- [ ] **Lifecycle stepper labels vs. real states.** `LifecycleStepper` uses `CORRELATED`/`APPROVAL` labels that don't match the actual `IncidentState` enum (`CORRELATING`/`AWAITING_APPROVAL`). Align the stepper's `steps` array keys exactly with `IncidentState` values so the `.includes()` fuzzy-matching hack can be replaced with an exact lookup — more correct and removes a subtle bug source.
- [ ] **Real alert/job counts instead of `evidence.length` proxies.** The incident queue sidebar shows `{evidence.length + 2} alerts · {Math.floor(evidence.length/2)} jobs` — cosmetic and misleading. Replace with the actual `alerts.length` (already fetched per-incident via `useIncidentData`) and a real `impact.filter(i => i.impact_type.includes('Job')).length`.
- [ ] **Loading skeletons instead of blank/"—" states.** Every panel (`Situation Header`, `Business Impact`, `Hypotheses`) shows a flat "—" or "Analyzing..." text while loading. Replace with proper skeleton shimmer placeholders (a `Skeleton` component using Tailwind's `animate-pulse`) — this alone will make the app feel dramatically more polished during the ~500ms–2s data-fetch windows.
- [ ] **Auth state indicator.** Already added a "Session Active / Not Authenticated" pill in `TopBar` (this change) — extend it to show the actual authenticated user's role/email once real login exists.

### 3.2 Agent Constellation — make it truly live
**Current state:** `AgentConstellation.tsx` renders based purely on `incident.status` string matching — it doesn't reflect which specific agent (RCA/Impact/Runbook/Critic) is actually running at that instant.
**Fix:** Since `_log_audit()` already fires distinguishable event types per agent (`HYPOTHESIS_CREATED`, `IMPACT_CALCULATED`, `RUNBOOK_RETRIEVED`, `SAFETY_VALIDATION_PASSED/FAILED`), thread the live SSE event stream (already consumed by `LiveOperationsConsole`) into `AgentConstellation` as well, so each agent node visually pulses/highlights in real time as its corresponding audit event arrives — turning it from a static status-based illustration into a genuinely live system diagram. This is a meaningful "wow factor" upgrade with no backend changes needed (data already exists).

### 3.3 Plan approval modal improvements
- [ ] Show the **plan version** and a **diff view** when a plan has been revised (`plan_version > 1`), so operators can see exactly what changed after feedback — currently a revision silently replaces the old plan with no visible trace of what was different.
- [ ] Add the safety-critic warning banner described in §2.3 above.
- [ ] Show **estimated blast radius / rollback difficulty** per step using the `risk_level` badge more prominently (currently a small mono-font pill) — add a colored left-border accent per risk tier (LOW=gray, MEDIUM=amber, HIGH=red) on each step card for faster visual scanning.

### 3.4 Empty/error states with actionable guidance
Per the architecture doc §9.4 and the enterprise roadmap's UX principles (§19.7), replace ambiguous states like "No recovery plan yet" with specific, actionable messaging:
- "Investigation not started — click **Triage Now** to begin" (with the button inline) instead of a passive blank state.
- "Investigation failed: {error} — [Retry]" when `triage_incident()` throws, instead of leaving the UI stuck showing nothing.
- Correlation ID / request ID shown in every error toast for support/debugging purposes.

### 3.5 Accessibility pass
- [ ] Add `aria-live="polite"` to the `LiveOperationsConsole` event list so screen readers announce new agent activity.
- [ ] Ensure severity/status pills are distinguishable by more than color alone (already partially done via text labels — verify icon or pattern redundancy for full WCAG 2.2 AA per the roadmap's Appendix E acceptance criteria).
- [ ] Keyboard navigation for the incident queue list (currently `motion.button` elements should already be focusable — verify tab order and add visible focus rings).

### 3.6 Design-system consistency
- [ ] Consolidate the ad hoc Tailwind color utility classes (`bg-critical/10`, `text-agent-active`, etc.) into a documented design-token reference (a short `docs/DESIGN_SYSTEM.md` or Storybook) so future contributors don't have to grep components to learn the palette.
- [ ] Standardize border-radius scale (`rounded-xl` vs `rounded-2xl` used somewhat inconsistently across cards) to a single scale (e.g., outer containers `rounded-2xl`, inner cards `rounded-xl`, pills `rounded-full`).

---

## Phase 4 — Functional / Architectural Hardening (Beyond Prototype)

These map directly onto Phase 0–2 of `nemoguard_enterprise_productization_roadmap.md`, scoped down to what's practical for a single-developer next iteration (not the full enterprise plan — that document remains the long-term reference).

### 4.1 Replace the mock-login dev flow with real authentication
Minimum viable real auth for a single-operator or small-team deployment:
- Integrate a real OIDC provider (Auth0, Okta, or even a simple self-hosted Keycloak) — swap `get_current_user()`'s JWT decode for JWKS-based validation against the provider's public keys instead of a shared symmetric `JWT_SECRET`.
- Build a real `/login` page in the frontend with a proper sign-in button, replacing the silent auto-fetch-mock-token behavior.
- This is the single highest-leverage change to make the app deployable outside your own machine.

### 4.2 Remove or clearly quarantine dead code paths
The architecture doc §13 documents ~30% of `src/` as unused relative to the live request path (legacy SQLite `database.py`/`schema.sql`, `mcp_server.py`/`read_tools.py`, `CommanderAgent`/`_save_dynamic_triage()`, Streamlit `ui/` files, unused `ToolRegistry`). Recommended action:
- Move genuinely unused code to a `legacy/` directory with a `README.md` explaining why it's kept (reference material) — don't delete outright yet in case some logic is worth salvaging (e.g. `ToolRegistry`'s policy-enforcement pattern is actually *better* than the live `agent_tools.py` and should be the target to migrate *toward*, not away from).
- Prioritize migrating the live agents (`rca_agent.py`, `dependency_agent.py`) to call through `ToolRegistry.execute_tool()` instead of directly calling `agent_tools.py` functions — this gets you real risk-based policy enforcement on agent tool calls for free, since the registry already implements it.

### 4.3 Introduce a governed action-execution pipeline
Bridge the gap between "fully simulated" and "real production actions" incrementally:
1. Pick **one low-risk, genuinely safe action** to make real first — e.g. `retry_pipeline_job` against the synthetic `execution` table (flip a row's `status` from `failed` to `succeeded` and re-run downstream dependency checks) is safe because it only touches your own demo data, not external systems.
2. Route it through `ToolRegistry.execute_tool()` (§4.2) so risk/approval policy is enforced end-to-end, not bypassed.
3. Add a real `verification_result` check (§2.4.1) that independently confirms the retry actually changed the state before marking the incident `RESOLVED`.
4. Only after this one real path is solid, consider wiring an actual external connector (Airflow API, Datadog API) per the stubs already scaffolded in `src/domain/connectors/`.

### 4.4 Durable workflow completeness
- [ ] Add a Temporal signal for "revise plan" (`revise_plan` signal) so `triage_feedback()` can be invoked *through* the running `IncidentLifecycleWorkflow` instead of as a side-channel synchronous API call — this makes the revision durable and keeps the workflow's approval-wait loop authoritative instead of racing with direct DB writes.
- [ ] Move from Temporal's **dev-mode server** (`temporal server start-dev`, in-memory, single-process) to a persisted Temporal deployment (Postgres-backed Temporal, or Temporal Cloud) once you need workflows to survive container restarts — currently an `api`/`temporal-worker` restart during an open incident can silently orphan the workflow state.

### 4.5 Testing foundation
There is currently no automated test suite covering the FastAPI endpoints or agent logic. Minimum viable test suite to add:
- [ ] `tests/test_plan_hash.py` — unit tests for `compute_plan_hash()` determinism and sensitivity to changes (already testable in isolation, zero dependencies).
- [ ] `tests/test_correlator.py` — unit tests for `CorrelatorEngine.calculate_pairwise_score()` and `correlate()` using synthetic `Alert` fixtures (also zero external dependencies, pure logic).
- [ ] `tests/test_api_auth.py` — integration test confirming `/triage`, `/approve`, `/execute`, `/feedback` return `401` without a valid token, and `/execute` returns `403` for a non-commander role.
- [ ] `tests/test_webhook_flow.py` — an end-to-end integration test (using `testcontainers` for a throwaway Postgres) that posts a synthetic webhook payload and asserts an incident is created — this is the "golden path" test recommended in the enterprise roadmap §28.2 and currently entirely missing.
- [ ] Add a GitHub Actions (or equivalent) CI workflow running `pytest` + `gitleaks` on every PR.

---

## Phase 5 — Suggested Execution Order

Given this is a solo/small effort, here is a realistic sequencing that yields visible value at every step rather than a long unreleased branch:

| Order | Work | Why now |
|---|---|---|
| 1 | Phase 0 (new key + `.env`) | App literally can't run without this |
| 2 | Verify Phase 1.1–1.3 changes work end-to-end (they're already applied) | Confirm nothing broke; these are the highest-severity fixes |
| 3 | §2.5 Severity string fix | 10-minute fix, removes a silent dashboard-accuracy bug |
| 4 | §3.1 Visual quick wins (stepper labels, real counts, skeletons) | Highest visual-impact-per-hour work |
| 5 | §2.1 Sequential LangGraph fix + §2.3 Critic gating | Meaningfully improves the credibility of the AI investigation for any demo |
| 6 | §3.2 Live Agent Constellation | High "wow factor," reuses existing data, no backend work |
| 7 | §2.7 Deterministic correlator as first-pass filter | Cost + correctness win, moderate effort |
| 8 | §4.5 Testing foundation (start with unit tests, they're cheap) | Prevents regressions as you keep iterating |
| 9 | §4.1 Real auth | Required before letting anyone else use this |
| 10 | §2.2, §2.4, §2.6, §4.2, §4.3, §4.4 | Deeper functional/architectural work, tackle opportunistically |

---

## Quick Reference — Files Changed in This Pass

| File | What changed |
|---|---|
| `src/domain/orchestrator.py` | Removed hardcoded API key |
| `src/domain/agents/base_agent.py` | Removed hardcoded API key |
| `simulator_backend/main.py` | Removed hardcoded API key, added explicit error if missing |
| `docker-compose.yml` | `NVIDIA_API_KEY`/`JWT_SECRET` now required env vars (fail-fast) |
| `src/api/auth.py` | Removed insecure default `JWT_SECRET`; added `ENV`-based dev-mode flag |
| `src/api/main.py` | Gated mock-login behind dev mode; added auth to mutating endpoints; added real plan-hash validation; added approve→execute fallback |
| `src/domain/plan_hash.py` | **New** — real plan content hashing |
| `.env.example` | **New** — documents all required env vars |
| `frontend/src/components/PlanApprovalModal.tsx` | Sends real `plan_hash` instead of fake value |
| `frontend/src/components/Dashboard.tsx` | Sends real `plan_hash` + auth token on execute |
| `frontend/src/App.tsx` | Added dev-mode auth token bootstrap + session status indicator |

Everything else in this document is a **planned**, not-yet-implemented improvement — prioritize per Phase 5's suggested order based on your available time and goals for the app.

---

## Phase 6 — UI/UX Redesign (Completed This Pass) & Remaining Polish

The dashboard has been rebuilt from a single 700-line monolithic component into a modular, event-driven "mission control" layout, directly implementing the design principles from `nemoguard_enterprise_command_center_ui_blueprint.md`.

### 6.1 What was rebuilt (done)

| New file | Purpose |
|---|---|
| `hooks/useIncidentEvents.ts` | Single shared SSE subscription per incident — used by both the Agent Constellation and the Live Operations Console so they are always perfectly in sync (previously each had its own independent, disconnected data source) |
| `components/AgentConstellation.tsx` (rewritten) | Now derives each of the 6 agent cards' state (`QUEUED`/`RUNNING`/`COMPLETED`/`FAILED`) directly from live SSE audit events matched by actor name and event type — not from a single coarse `incident.status` string. Agents visibly pulse the instant their corresponding backend event fires. |
| `components/dashboard/shared.tsx` | Extracted formatters, badges, `LifecycleStepper` (now matches the real `IncidentState` enum exactly instead of fuzzy-matching invented labels), and a reusable `EmptyState` component with icon + title + actionable subtitle |
| `components/dashboard/IncidentQueue.tsx` | Left rail; queue is now sorted "needs approval / needs review" first (per the blueprint's queue-ordering spec), with a `ShieldAlert` icon marking incidents awaiting a safety decision |
| `components/dashboard/SituationHeader.tsx` | Top situation card; added an inline **"Start Triage Now"** button when an incident is sitting in `DETECTED` with no investigation running yet (previously the operator had no way to trigger this from the UI at all — the only entrypoint was the simulator) |
| `components/dashboard/InvestigationPanels.tsx` | Alerts, Agent Constellation + Hypotheses row, Activity Console + Business Impact row — all using specific `EmptyState`s ("RCA Agent is investigating logs…" / "No hypothesis formulated yet — start triage to begin") instead of the previous ambiguous blank cards or raw "—" |
| `components/dashboard/RecoveryRail.tsx` | Right rail; now renders a **Safety Review banner + explicit acknowledgement checkbox** when a plan's status is `NEEDS_REVIEW` (wired to the new backend gating in `orchestrator.py`) — the Approve button is disabled until the operator explicitly ticks "I have reviewed the safety concern" |
| `components/dashboard/EvidenceModal.tsx` | Extracted evidence/grounding modal, unchanged behavior but isolated for maintainability |
| `components/LiveOperationsConsole.tsx` (rewritten) | No longer owns its own `EventSource` — takes `events`/`status` as props from the shared hook; added `aria-live="polite"` for screen readers |
| `components/Dashboard.tsx` (rewritten) | Reduced from ~700 lines of inline JSX to a ~170-line composition root wiring the above pieces together — the entire dashboard is now testable and readable component-by-component |

### 6.2 Backend changes that support the new UI (done)

- `orchestrator.py::save_agent_findings()` now accepts `critic_passed`/`critic_feedback` from the LangGraph investigation and sets `action_plan.status = 'NEEDS_REVIEW'` (instead of the generic `PENDING_APPROVAL`) when the Grounding Critic (Safety Agent) flags the plan — the safety gate now has a real, distinct, UI-visible state instead of being silently ignored.
- `POST /triage` is now callable directly from the frontend (used by the new "Start Triage Now" button), requiring authentication like the other mutating endpoints.

### 6.3 Verified live end-to-end (this pass)

Using the real running stack (new NVIDIA key, both `nemotron-3-ultra-550b-a55b` for RCA/Critic and `nemotron-3-super-120b-a12b` for Impact/Runbook/Watcher):
- Triggered a live scenario → Watcher Agent correlated 3 alerts into one incident in the UI in real time.
- Agent Constellation cards visibly transitioned `QUEUED → RUNNING` for RCA and Runbook agents as their audit events streamed in, confirming the event-to-card wiring works correctly with real backend data, not just mocked state.
- Fixed a real layout bug found during visual QA: the severity/ID/status badge row in `SituationHeader` did not wrap on narrower viewports and visually collided with the SLA-breach card — fixed with `flex-wrap` and a `max-w` truncation on the incident ID.

### 6.4 Remaining visual/UX polish (not yet implemented — prioritized)

1. **Plan diff view on revision.** When a plan's `plan_version > 1` (revised via feedback), show a two-column before/after diff of rationale + steps in `PlanApprovalModal` instead of only showing the latest version with no visible history.
2. **Risk-tiered step styling.** In `PlanApprovalModal`, add a colored left-border accent per step card based on `risk_level` (LOW=gray, MEDIUM=amber, HIGH=red) so an approver can risk-scan the plan without reading every line.
3. **Loading skeletons.** Replace the text-based `EmptyState` "loading" variants with actual skeleton-shimmer placeholders (Tailwind `animate-pulse` blocks shaped like the real content) for the ~1-3 second windows between incident selection and first data arriving — currently a plain centered message, which is fine but not best-in-class.
4. **Causal-chain / dependency graph view.** The blueprint calls for three graph modes (Causal Chain, Technical Topology, Business Lineage) using a proper graph library (e.g. React Flow). Currently "Live causal chain" is a simple horizontal chip list of the first 4 evidence items — functional but not a real graph visualization. This is the single largest remaining gap versus the full blueprint vision and the best next investment if you want the "wow factor" of seeing the actual dependency topology light up red→amber→green as the incident resolves.
5. **Execution progress view.** When a plan moves to `EXECUTING`/`VERIFYING`, the Recovery Rail should morph into a live step-by-step checklist (✓ Approval recorded → ✓ Step 1 executed → ● Verifying → ○ Downstream check) per blueprint §13.4. Currently the rail shows the same 5-item "formulation status" list regardless of whether the plan is still being drafted or is actively executing — these are conceptually different moments and deserve different UI.
6. **Design tokens document.** Consolidate the Tailwind color/spacing conventions already in use (`bg-critical/10`, `text-agent-active`, 8px spacing scale) into a short `docs/DESIGN_SYSTEM.md` so future additions stay consistent without grepping existing components.
7. **Accessibility pass.** Keyboard-focus rings on the incident queue buttons, `prefers-reduced-motion` handling for the Framer Motion animations, and a screen-reader-only live region announcing incident state transitions (beyond the `aria-live` already added to the event console).
8. **Real-time toast notifications.** `react-hot-toast` is already wired in but unused (`Toaster` renders with nothing feeding it) — hook it up to fire a toast on new incident creation and on plan-ready/safety-review-required transitions, so an operator glancing away from the dashboard doesn't miss a new SEV-1.
