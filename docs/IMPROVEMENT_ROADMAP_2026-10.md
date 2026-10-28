# NemoGuard Product & Reliability Improvement Roadmap

**Created:** 2026-10-19  
**Status:** Phases 1–2 partially complete; Phase 2 route-family audit remains
**Purpose:** Improve incident-response effectiveness by making safety behavior, tenant boundaries, operational signals, and UI freshness reliable and testable. This roadmap prioritizes trustworthy behavior over adding more feature surface.

## Guiding principles

1. **Never claim resolution without proof.** All required actions must execute successfully and independently verify.
2. **Scope every operation to its tenant and parent resource.** Resource IDs from different incidents or tenants must never be mix-and-matched.
3. **Accepted work must survive process failure.** A 202 response must mean work is durably queued or persisted.
4. **Separate observations from model conclusions.** Surface provenance, uncertainty, freshness, and missing evidence.
5. **Make failures visible without hiding last-known-good data.** UI should report stale/partial state and recover predictably.
6. **Expand coverage with adversarial tests.** Security and safety invariants need negative as well as happy-path tests.

## Phase 1 — Verified execution must gate resolution (P0)

**Scope**
- Correct `IncidentOrchestrator.execute_plan()` so a plan can resolve an incident only when it contains required work and every action has a successful result plus `VerificationStatus.PASSED`.
- Treat failed, precondition-failed, policy-denied, skipped, inconclusive, or missing action outcomes as unresolved/escalated.
- Define and enforce empty-plan behavior (fail closed; never resolve vacuously).
- Ensure aggregate plan status and incident state accurately reflect partial execution.

**Acceptance criteria**
- No plan with zero actions reaches `RESOLVED`.
- No action whose execution status is not success can contribute to resolution, even if verification is skipped or anomalously says passed.
- No action with verification other than `PASSED` can contribute to resolution.
- All-success/all-passed execution resolves as before.
- Regression tests cover success, execution failure, policy denial, precondition failure, skipped/inconclusive verification, and empty plan.
- Targeted tests and the relevant broader suite pass.

## Phase 2 — Bind plans and child resources to incident/tenant (P0)

**Scope**
- Require `action_plan_id` and `incident_id` to match for approval, execution, plan listing/use, and related state changes.
- Enforce ownership again inside the domain execution service, not only in the HTTP route.
- Review sub-resource and admin endpoints for tenant scoping, including context alerts/logs, global alerts, Teams deliveries, replay/evaluation resources, and Commander records.
- Add exhaustive route-family cross-tenant and cross-incident tests.

**Acceptance criteria**
- A caller cannot combine an incident from one tenant with a plan from another incident.
- A caller cannot read/mutate another tenant’s records through context, alert, notification, replay, or evaluation APIs.
- Existing valid same-tenant workflows remain functional.
- Tests enumerate protected endpoint families and verify 404/403 semantics consistently.

## Phase 3 — Strict approval semantics and durable audit (P1)

**Scope**
- Restrict approval decisions to a defined enum and validate current plan state, expiry, and plan hash.
- Persist approval decision and corresponding plan state atomically.
- Make audit messages reflect approve/reject accurately.
- Ensure Temporal and fallback behavior have equivalent invariants and idempotency.

**Acceptance criteria**
- Invalid decisions are rejected before writes.
- Approval records have meaningful timestamps and expiry semantics.
- Duplicate requests cannot execute a plan twice.
- Rejection does not mark plans approved or execute them.
- Tests cover race/retry behavior, Temporal signal success/failure, and fallback.

## Phase 4 — Durable asynchronous processing (P1)

**Scope**
- Replace in-process `asyncio.create_task` for accepted webhook, replay, and evaluation jobs with durable queue/workflow dispatch.
- Make webhook acknowledgment happen only after durable acceptance.
- Replace the global webhook correlation lock with database-safe idempotency/locking that avoids serializing unrelated incidents.
- Add retry, timeout, dead-letter/error visibility, and operational metrics.

**Acceptance criteria**
- Restarting the API after acceptance does not lose work.
- Duplicate webhook delivery is idempotent.
- Independent incidents can be processed concurrently.
- Failed jobs are visible and recoverable; no task failure exists only in console output.

## Phase 5 — Truthful metrics and evidence provenance (P1)

**Scope**
- Remove hardcoded/estimated overview values or label them explicitly as estimates/unavailable.
- Ensure metrics named “today” are time-bounded and semantically correct.
- Emit safety-validation audit events only when the corresponding check actually ran and passed.
- Persist precise support/contradiction/missing-evidence links per hypothesis; distinguish observed facts, derived facts, model claims, and operator input.

**Acceptance criteria**
- Every displayed metric has a defined source, time window, and calculation.
- Unknown inputs render as unknown rather than fabricated values.
- Audit “passed” records are backed by persisted check results.
- Evidence links are traceable and do not imply unsupported grounding.

## Phase 6 — Frontend resilience and accessible operations (P2)

**Scope**
- Check HTTP status and validate response shape in incident data hooks; represent partial failures and last successful refresh time.
- Reduce redundant polling; use visibility-aware polling, backoff, cancellation/deduplication, and event-driven invalidation where appropriate.
- Add keyboard-accessible incident row navigation and clear focus semantics.
- Make stale/partial data, active execution, and verification state explicit across dashboard/workspace.
- Review Commander claims for evidence links and appropriately scoped summaries.

**Acceptance criteria**
- API errors cannot silently appear as empty or partially valid incident data.
- Hidden pages do not maintain unnecessary high-frequency polling.
- All incident selection and major actions are keyboard accessible.
- Operators can identify stale data and the source/time of the last successful update.
- State labels distinguish approved, executing, executed, verifying, resolved, and failed verification.

## Phase 7 — Maintainability, setup, and release confidence (P2)

**Scope**
- Split the oversized FastAPI module into domain/API routers and move SQL/business rules behind service boundaries.
- Standardize typed request/response schemas and error responses.
- Update README setup/test instructions to match `pyproject.toml`, current routes, and current product terminology.
- Verify secret/private-key ignore and tracking status without exposing secret contents; rotate anything that may have been committed.
- Add lifecycle-level end-to-end acceptance tests and CI gates for backend/frontend checks.

**Acceptance criteria**
- A clean checkout can follow documented setup and run tests.
- Auth, incident, admin, Commander, replay, and notification routers have clear ownership.
- CI runs type/build/lint/unit tests and configured integration tests.
- No secret, private key, or sensitive runtime log is tracked in Git.

## Implementation sequence and change control

- Work one phase at a time in priority order.
- For each phase: inspect current behavior, add/adjust tests first where practical, implement the smallest safe change, run targeted tests, run relevant broader checks, then update this roadmap with outcomes and remaining risks.
- Do not claim a security issue is fixed based solely on code inspection; prove it with an adversarial test.
- Do not deploy automatically unless the user explicitly asks; deployment actions require separate approval.
- Keep commits focused by phase and avoid touching unrelated local artifacts.

## Progress log

### 2026-10-19
- Assessment completed from repository structure, key UI flows, API/auth code, policy/execution code, and cross-tenant integration tests.
- Phase 1 selected as first implementation target due to the potential for false incident resolution.
- Implemented Phase 1:
  - Added `is_resolution_verified()` in `src/capabilities/execution_engine.py`.
  - A required action now qualifies only when its result is `SUCCESS` and independent verification is `PASSED`.
  - Updated `IncidentOrchestrator.execute_plan()` to use this predicate for every executed step.
  - Empty plans now fail closed as `MANUAL_ACTION_REQUIRED`, are audited, and cannot resolve an incident.
  - Added `tests/unit/test_execution_engine.py`, covering every execution and verification enum combination.
- Validation:
  - `.venv/bin/python -m pytest tests/unit/test_execution_engine.py -q` — **10 passed**.
  - `.venv/bin/python -m py_compile src/capabilities/execution_engine.py src/domain/orchestrator.py` — **passed**.
  - One pre-existing Pydantic v2 class-config deprecation warning remains; it is outside Phase 1 scope.
- Implemented the plan-to-incident ownership portion of Phase 2:
  - Added `_require_plan_for_incident()` in `src/api/main.py`.
  - Direct execution now verifies the caller's tenant-scoped incident and requires the supplied plan to belong to that incident.
  - Approval now loads the action plan using both `action_plan_id` and `incident_id`, preventing a valid plan hash from bypassing parent-resource ownership.
  - `IncidentOrchestrator.execute_plan()` independently checks `action_plan.incident_id` before loading steps or mutating any plan/incident state.
  - Added real-service regression coverage that attempts to approve and execute incident B's plan through incident A's URL in the same tenant.
- Validation:
  - Initial integration run correctly exposed that the already-running API container was serving the prior image; it returned the vulnerable behavior.
  - Rebuilt and restarted only the `api` Compose service with the changed source.
  - `set -a && source .env && set +a && .venv/bin/python -m pytest tests/integration/test_multi_tenancy.py::TestPlanIncidentBinding -q` — **2 passed**.
- Remaining Phase 2 work: audit and add adversarial coverage for context, global alerts, Teams, replay, evaluation, and Commander route families.
