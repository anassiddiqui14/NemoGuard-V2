# NemoGuard Pipeline Copilot — Current Status & Design Report

**Generated:** 2026-08-23 · **Branch:** `enterprise-hardening` @ `8632317` (+ uncommitted work this session)
**Scope:** `pipeline-copilot/` (the actual running application). Supersedes `docs/APP_STATUS_REPORT_2026-08-21.md`.

**Purpose:** An accurate, code-verified snapshot of what the app *is today*, so the next work session can pick up cleanly. Every claim below was checked directly against running containers, live database rows, or a passing test run in this session.

---

## 1. Executive Summary

Since the 2026-08-21 report, work has focused on three areas: (1) fixing a real production bug where the frontend couldn't reach the API through the Docker proxy, (2) adding a proper human-in-the-loop **Cancel Incident** control to the dashboard (previously present in the backend but with zero UI access), and (3) building a new **Scenario Cockpit** page — a visual control surface for triggering both scripted and *genuinely real* AWS-emulated failures (via the existing LocalStack lab) directly from the browser, replacing the need to run CLI scripts by hand.

**Verified live in this session:**
- **141/141 unit tests pass.**
- All 8 core containers running and healthy (`postgres`, `temporal`, `api`, `temporal-worker`, `frontend`, `simulator`, `localstack`, `redis` — `redis` is new since the last report and not yet documented/explained in this codebase's docs).
- **End-to-end real-AWS incident creation was proven live**: triggering "Schema Drift" from the new cockpit UI caused a real Lambda `KeyError`, tripped a real CloudWatch alarm, was relayed by an in-process forwarder thread, and NemoGuard created a brand-new incident that the agent pipeline immediately picked up into `INVESTIGATING`.
- A **pre-existing correlator behavior** was surfaced (not introduced) during this testing: the LLM-based correlator will match a new real alert to a previous incident by alarm-name/service proximity even when that prior incident is already in a terminal `FAILED` state, rather than only correlating against currently-open incidents. This is a genuine finding worth a decision (see §4.1).

---

## 2. This session's changes (uncommitted, on top of `8632317`)

| Area | What | Verified |
|---|---|---|
| **Frontend↔API proxy fix** | `frontend/nginx.conf` rewritten to resolve the `api` Compose service at request time via Docker's internal DNS (`127.0.0.11`) instead of caching a stale container IP, and to preserve the full request URI (`$request_uri`) when proxying through a variable upstream. Root cause of an intermittent `502 Bad Gateway` that made the dashboard appear to have no incidents. | ✅ Live: `/api/v2/status` and authenticated `/api/v2/incidents` both return 200 through the proxy; confirmed via browser. |
| **Cancel Incident UI** | New `CancelIncidentModal.tsx` + wiring in `IncidentWorkspace.tsx`/`SituationHeader.tsx`. The backend's `POST /api/v2/incidents/{id}/cancel` (a real Temporal signal) has existed since WP-004 but had **no UI entry point at all**. The button is correctly gated to only appear when `status === AWAITING_APPROVAL`, matching the backend's actual state-machine-enforced legal transition (attempting cancel from `INVESTIGATING`, etc. returns HTTP 409). | ✅ Live: cancelled a real `AWAITING_APPROVAL` incident via the new modal; confirmed transition to `CANCELLED` in the DB and disappearance from the active queue. |
| **Scenario Cockpit** | New page (`ScenarioCockpitPage.tsx`) + nav entry, reachable at `/app/scenario-cockpit`. Three sections: (1) existing scripted webhook scenarios, (2) **new**: real AWS-lab triggers (Lambda/S3/Step Functions via LocalStack) exposed as HTTP endpoints on `simulator_backend` (`/lab/status`, `/lab/trigger/{ingest,order_events,notification,pipeline}`), with an in-process background thread that continuously forwards real CloudWatch alarms into NemoGuard's webhook endpoint (previously required manually running `localstack_lab/forwarder.py` in a separate terminal), (3) existing Generative-AI free-text scenario generator. | ✅ Live end-to-end: see Executive Summary. |
| **Docker/build plumbing** | `simulator_backend/Dockerfile.simulator` rebuilt to use the repo root as build context (so it can bundle `localstack_lab/` + `boto3`); `docker-compose.yml` updated to match; `frontend/nginx.conf` gained an `/sim/` proxy block mirroring the existing `/api/` one. | ✅ Rebuilt and redeployed; confirmed reachable through the frontend origin only (no direct browser→8001 calls). |
| **LocalStack lab provisioning** | The lab's S3 bucket, 3 Lambdas, CloudWatch alarms, SNS topic, 2 SQS queues, and Step Functions state machine were not yet provisioned in this environment; provisioned this session (idempotent — safe to re-run). | ✅ Confirmed via `/lab/status` returning `available: true`. |

**Not yet committed to git** — all of the above exists only in the working tree (see `git status --short` in this session; nothing has been committed since `8632317`).

---

## 3. Known gaps carried over from the 2026-08-21 report (unchanged unless noted)

1. **Temporal is still dev-mode** (in-memory, no TLS, no persistent Temporal DB, no HA) — highest-impact gap, unchanged.
2. **Capability gateway coverage is narrow** — still only 6 registered capabilities; unchanged.
3. **Observability wired but not operationalized** — OpenTelemetry present, no real trace backend/dashboards/alerting; unchanged.
4. **`test_incident_workflow.py` flakiness** — documented, non-deterministic under this sandbox's Temporal test-server clock-skipping; unchanged, and now shows a `run_temporal_durability_test.py` / `run_compose_temporal_durability_test.py` pair of new (uncommitted) scripts exist in `scripts/`, suggesting a durability-test pass may have already been attempted this cycle — worth checking their output/README before re-running.
5. **`src/ui/` legacy Streamlit dashboard** — still present, still dead code, still not deleted.
6. **`incident_impact.impact_score` under-populated** — status unknown this session; `migrations/009_business_impact_engine.sql` and `src/domain/impact_engine.py` are new (uncommitted) files that strongly suggest this exact gap (§4.7 in the prior report) has since been worked on — needs a fresh look to confirm whether it's done, in-progress, or just scaffolded.

## 4. New findings from this session

### 4.1 Correlator matches into terminal (non-open) incidents
Observed live: a freshly-fired real CloudWatch alarm was correlated (0.95 confidence, LLM-reasoned) into `INC-21EBEF84`, an incident already in `FAILED` status from 11 days prior — purely because the alarm name and service matched, with no check on whether the target incident was still actually open/actionable. This means a resolved-or-failed incident can silently "reopen" (or at least accumulate new evidence) instead of a fresh incident being created. Whether this is desired behavior (e.g., "this exact failure mode recurred, attach as new evidence to the historical record") or a bug (a live, actionable incident should probably not correlate against a dead one) is a product decision, not something this session should have unilaterally changed. Worth explicit triage next session.

### 4.2 `redis` service now running but undocumented
`nemoguard-redis` (healthy) is running in this environment but isn't mentioned in the 2026-08-21 report's service table, isn't in the `docker-compose.yml` diff reviewed this session under `M` (modified), and its actual purpose in the current codebase wasn't investigated this session. Needs a quick audit: is this an intentional new dependency (e.g., rate-limiter backend, session cache) already wired into code, or a leftover from experimentation?

### 4.3 Uncommitted scope is large and mixed
The current working tree combines this session's cockpit/proxy/cancel-UI work with what appear to be **separate, unrelated in-progress changes** already present before this session started: `src/domain/impact_engine.py`, `migrations/009_business_impact_engine.sql`, `tests/unit/domain/test_impact_engine.py`, `src/capabilities/plan_compiler.py` modifications, `tests/unit/test_plan_compiler.py`, and two Temporal durability-test scripts. None of this was authored in this session, but it's all sitting uncommitted alongside this session's changes. **Recommend splitting into separate commits** (or at minimum reviewing each cluster individually) before merging, rather than one large mixed commit.

---

## 5. Suggested next priorities (for review)

1. **Triage the uncommitted "impact engine" and "plan compiler" work** (§4.3) — determine what it is, whether it's finished, and commit it separately from this session's cockpit/proxy/cancel-UI changes.
2. **Decide the correlator's terminal-incident-matching behavior** (§4.1) — product decision with a real, demonstrated live example to reason from.
3. **Audit the new `redis` service** (§4.2) — confirm intended purpose before it becomes "mystery infrastructure."
4. **Commit this session's work** (cockpit, proxy fix, cancel UI) as its own clean commit(s) once the above is disentangled.
5. Carried-over from the prior report, still unaddressed: Temporal production deployment (§3.1), capability gateway expansion (§3.2), observability operationalization (§3.3), `src/ui/` deletion (§3.5).
