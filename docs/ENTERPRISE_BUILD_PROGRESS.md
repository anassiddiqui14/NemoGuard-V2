# Enterprise-Scale Build — Progress Log

Tracks real, implemented progress against
`docs/nemoguard_real_world_support_engineer_build_spec.md` (the GPT-authored
enterprise spec) and `docs/IMPLEMENTATION_PLAN_FROM_GPT_SPEC.md` (the
scoped-down phased plan). This is a running log — update it as each phase
lands, don't rewrite history.

## Phase 1 — Governed Capability Gateway ✅ DONE (foundational layer)

Per spec §12 and §39 ("Immediate next actions"), this was built FIRST
because everything else (evidence fabric, hypothesis ledger, domain skill
packs, UI) depends on having a real, typed, verifiable execution substrate
instead of free-text plan steps.

**Built (`src/capabilities/`):**
- `models.py` — `ActionIntent`, `CompiledAction`, `CompiledPlan`,
  `ActionResult`, `VerificationOutcome`, `CapabilityDefinition` (spec §33
  Pydantic contracts, adapted to the current codebase).
- `registry.py` — the capability catalog (spec §12.2). 6 real capabilities
  registered, each with `precondition_check` / `execute` / `verify` as
  separate callables:
  - `data.check_table_staleness` (READ_ONLY, AUTOMATIC)
  - `data.cleanup_partial_write` (MEDIUM, HUMAN_APPROVAL_REQUIRED, dry-run-first)
  - `data.idempotent_rerun_order_events_job` (MEDIUM, HUMAN_APPROVAL_REQUIRED)
  - `compute.rerun_ingest_job` (MEDIUM, HUMAN_APPROVAL_REQUIRED)
  - `ops.verify_row_count_matches_expected` (READ_ONLY, AUTOMATIC)
  - `ops.manual_step` (fallback for anything unmapped; always
    `INCONCLUSIVE` verification, never auto-passes — satisfies spec §37.7
    "no self-verification")
- `plan_compiler.py` — deterministic `ActionIntent -> CompiledAction`
  resolution + SHA-256 plan hashing (spec §12.5). No LLM output is trusted
  to name a capability directly.
- `policy.py` — deterministic risk/autonomy -> approval-requirement
  mapping in CODE, not prompts (spec §13.1, §37.6).
- `execution_engine.py` — the generic
  precondition-check -> execute -> INDEPENDENT-verify engine (spec §12.6,
  §14.1). Zero capability-specific branching outside `registry.py`.
- `intent_mapper.py` — compatibility bridge so the EXISTING free-text
  `action_step.tool_name`/`action_type` strings (already being produced by
  the RCA/Runbook/Commander agent prompts) can flow through the new
  pipeline today, without first requiring every agent prompt to emit
  structured JSON.

**Wired into production (`src/domain/orchestrator.py::execute_plan`):**
Replaced the old hardcoded behavior:
```python
# BEFORE (removed):
conn.execute("UPDATE action_step SET status = 'SUCCEEDED' ...")
conn.execute("INSERT INTO verification_result (...) VALUES (..., 'PASSED', ...)")  # x2, always
conn.execute("UPDATE incident SET status = 'RESOLVED' ...")  # unconditional
```
with a real per-action loop that compiles, executes, and independently
verifies each step, and ONLY marks the incident `RESOLVED` if every action's
verification actually passed — otherwise `FAILED` + an `INCIDENT_ESCALATED`
audit event.

**DB migration:** `migrations/005_capability_gateway.sql` (applied to the
running Postgres) — adds `capability_id`/`capability_version` to
`action_step`, `compiled_plan_hash` to `action_plan`, and
`capability_id`/`verification_status`/`verification_details_json` to
`action_execution`.

**Verified end-to-end against REAL infrastructure (not mocked):**
1. Triggered a genuine partial-write crash in the LocalStack lab
   (`break_order_events_scenario.py partial_write_crash`) — 5/10 rows
   really committed to Postgres before a real Lambda crash.
2. Ran the full compile → policy-evaluate → execute → verify pipeline
   directly: `data.check_table_staleness` correctly detected
   `is_stale_or_partial: true`; `data.idempotent_rerun_order_events_job`
   (requiring approval per policy) cleaned up, reran, and verified
   `actual_row_count: 10, verified: true`.
3. Ran the exact PRODUCTION code path (`IncidentOrchestrator.execute_plan`)
   against a real incident/plan/step row set: confirmed
   `action_step.status = SUCCEEDED`, `capability_id = data.check_table_staleness`,
   `action_execution.verification_status = PASSED`, and
   `incident.status = RESOLVED` — all derived from real independent
   verification, not a hardcoded assumption.
4. API + temporal-worker containers rebuilt and redeployed with zero
   import/startup errors.

## Phase 2 — Real evidence fabric + change intelligence ✅ DONE

Per spec §9.2 (Authority) and §8.8 (Change Intelligence).

**Built:**
- `src/domain/evidence_authority.py` — deterministic
  `classify_authority(source_system) -> AUTHORITATIVE|HIGH|MEDIUM|LOW`,
  computed in code (not inferred by an LLM), matching spec §9.2. Wired
  into `orchestrator.save_agent_findings`'s evidence-insert path.
- **Migration** `006_evidence_authority.sql` — adds `evidence.authority`
  column, backfilled 17 existing rows.
- `list_recent_changes(resource_id, window_minutes)` in
  `aws_observability_tools.py` — change-intelligence tool (spec §8.8).

  **Important real-world finding documented in code:** CloudTrail's
  `LookupEvents` API is confirmed (by direct testing against the running
  LocalStack container) to be a **LocalStack Pro-only feature** — it
  returns `"API for service 'cloudtrail' not yet implemented or pro
  feature"` on the free tier we're using. Per the spec's own "degrade
  safely, never fake success" principle (§37.4 / non-negotiable #16),
  rather than mocking CloudTrail data, the tool uses a genuinely
  real, free-tier-available signal instead: the target Lambda's actual
  `LastModified`/`RevisionId`/`CodeSha256` from `get_function` (a real
  code/config update genuinely changes these fields). CloudTrail is
  layered on top as an *additional* signal when available, with an
  explicit `warnings` field surfaced when it isn't — never silently
  dropped or faked.
  **Verified against real infrastructure**: correctly reported
  `age_minutes: 616.5`, `within_window: false` for a real Lambda,
  alongside a transparent CloudTrail-unavailable warning.
- Wired into `agent_tools.py` schema/dispatcher and the RCA agent's
  prompt ("ALWAYS call this for the primary failing resource... before
  concluding root cause, not after").

## Phase 3 — Hypothesis-driven investigation (ledger, not full LangGraph loop) ✅ PARTIAL

Per spec §10.1 (Hypothesis Ledger). Full §10.2-§10.4 (iterative
evidence-seeking loop with stop conditions, tool-selection-by-information-
gain) is NOT yet built — this phase covers the ledger data structure and
getting the RCA agent to actually populate it.

**Built:**
- Updated `rca_agent.py`'s system prompt + JSON schema: the agent must
  now return a `hypotheses: [...]` array (at least 2 competing hypotheses,
  each with `statement`, `cause_type`, `confidence`,
  `supporting_evidence_titles`, `contradicting_evidence_titles`) instead
  of collapsing everything into one `finding` string.
- `orchestrator.triage_incident` now passes through the RCA agent's full
  ranked hypothesis list to `save_agent_findings` (which already writes
  one row per hypothesis to the `hypothesis` table, using the existing
  `rank_no`/`supporting_evidence_json`/`contradicting_evidence_json`
  columns) instead of collapsing to a single hypothesis. Falls back to a
  single-hypothesis list for backward compatibility with older RCA
  responses.

**Also built in this phase — Grounding Critic independent verification
(spec §7.1):**
- `agent_tools._get_read_only_tools_schema()`: a filtered tool schema that
  excludes every write/action capability (currently just
  `cleanup_partial_write`), leaving all 19 read-only diagnostic tools
  available. This is the mechanism that structurally guarantees the
  critic can verify but never act — enforced by which tools it's even
  given access to, not by prompt instruction alone.
- `GroundingCritic` rewritten to use `call_llm_with_tools` (previously
  `call_llm_json`, which had zero tool access at all) with this read-only
  schema, and its prompt now explicitly instructs it to independently
  re-verify specific factual claims (e.g. re-check a log line or a
  table's staleness) rather than just trusting the RCA/Impact/Runbook
  agents' text.
- **Verified live**: confirmed via container logs that the Grounding
  Critic genuinely calls tools during real investigations (observed
  `[Grounding_Critic] Calling LLM with 19 tools...` and real tool
  executions of `query_logs` and `verify_row_count_matches_expected`
  during a live triage run) — this is a structural capability upgrade
  that is actually exercised, not just wired and unused.

**Still not yet done** (tracked for a future session): the investigation
is still a fixed LangGraph flow rather than a fully iterative
evidence-seeking loop with information-gain-based tool selection and
explicit stop conditions (spec §10.2-§10.4); confidence is not yet
calibrated against historical accuracy (spec §10.5).

## Phase 3.5 — Admin-configurable capability policy ✅ DONE

Per spec §3.2 (Capability certification record) and §17.4 (Policy
administration), scoped down per `docs/IMPLEMENTATION_PLAN_FROM_GPT_SPEC.md`
Part 2.2: a single YAML file rather than a full certification/evaluation-
suite subsystem.

**Built:**
- `config/capability_policy.yaml` — one entry per registered capability,
  each with a `risk_level`/`autonomy_mode` override. A capability not
  listed uses its Python-defined default (`registry.py`).
- `src/capabilities/policy.py` — `_load_overrides()` reads and caches this
  YAML (path overridable via `NEMOGUARD_CAPABILITY_POLICY_PATH` env var
  for testing); `_effective_risk_and_autonomy()` merges YAML override over
  the code default; `reload_policy_config()` exposed for a future admin
  API endpoint to force a live reload without a process restart.
  Fail-safe: a missing file, parse error, or unknown capability_id in the
  YAML silently falls back to the Python default — a config typo can
  never silently grant MORE access than the code allows.
- `src/capabilities/execution_engine.py` — added a **Step 0 policy
  re-check** at execution time (not just approval time): if
  `policy.evaluate_action()` returns `DENIED` for the compiled action's
  *current* effective policy, execution is refused before preconditions
  are even checked, and a structured `FAILED`/`SKIPPED` result+verification
  is returned with the policy reasons. This closes the gap where a plan's
  policy could otherwise be checked once at approval time and then
  bypassed by any later direct call to `execute_compiled_action`.

**Verified live:**
1. Confirmed default (code-only) policy decision for
   `data.cleanup_partial_write`: `REQUIRE_APPROVAL`.
2. Wrote a temporary override YAML setting that same capability's
   `risk_level`/`autonomy_mode` to `PROHIBITED`, pointed
   `NEMOGUARD_CAPABILITY_POLICY_PATH` at it, and confirmed the decision
   changed to `DENIED` — with zero code changes, purely from config.
3. Confirmed the execution engine actually enforces this: overriding
   `data.check_table_staleness` (normally `READ_ONLY`/`AUTOMATIC`) to
   `PROHIBITED` and calling `execute_compiled_action` directly returned
   `result.status = FAILED` with `error_message = "Policy denied
   execution: Capability data.check_table_staleness is prohibited by
   policy."` — confirming the policy gate is enforced at the moment of
   execution, not just at compile/approval time.
4. Confirmed the non-overridden path is unaffected: the same capability
   without any override still executes normally (`SUCCESS`/`PASSED`).
5. Rebuilt and redeployed `api`+`temporal-worker`; confirmed
   `/api/v2/status` healthy post-deploy.

## Phase 3.6 — Admin API for capability catalog (spec §17.3) ✅ DONE

**Built (`src/api/main.py`):**
- `GET /api/v2/admin/capabilities` (admin-only via `require_role("admin")`)
  — lists every registered capability with its `default_risk_level`/
  `default_autonomy_mode` (from `registry.py`) AND its
  `effective_risk_level`/`effective_autonomy_mode` (after applying any
  `config/capability_policy.yaml` override), plus an `overridden: bool`
  flag. Critically, this endpoint runs the SAME `policy._effective_risk_and_autonomy()`
  function the real execution engine uses — there is no separate/divergent
  "display-only" policy logic that could drift out of sync with runtime
  behavior.
- `POST /api/v2/admin/capabilities/reload-policy` (admin-only) — forces
  the next policy evaluation to re-read `capability_policy.yaml` from
  disk, so an admin editing the file doesn't need to restart the API
  process for the change to take effect.

**Verified live:**
1. `GET /api/v2/admin/capabilities` with an `admin` role token returned
   the full real catalog of 6 capabilities with correct default/effective
   values for all of them.
2. The SAME request with a `viewer` role token was correctly rejected:
   `403 {"detail":"Not enough permissions"}` — RBAC is genuinely enforced.
3. `POST /api/v2/admin/capabilities/reload-policy` with an admin token
   returned `{"status":"reloaded","config_path":"/app/config/capability_policy.yaml"}`
   — confirming it resolved the real in-container config path.
4. Rebuilt and redeployed `api`; confirmed all endpoints respond
   correctly post-deploy.

## Phase 3.7 — Surfacing the hypothesis ledger + evidence authority in the UI ✅ DONE

Phases 2 and 3 built real backend data (evidence.authority, ranked
hypotheses) that was invisible to actual operators — the frontend
silently discarded it. This phase closes that gap.

**Found and fixed a real bug in `useIncidentData.ts`:** the hook fetched
the full `hypData` array from `/api/v2/incidents/{id}/hypotheses` (which
already returns every ranked hypothesis, ordered by confidence DESC) but
then did `const rawHyp = hypData[0]` and discarded the rest — so every
alternative hypothesis the RCA agent generated, ranked, and attached
supporting/contradicting evidence to was silently thrown away before it
ever reached the UI.

**Built:**
- `useIncidentData.ts` — added a `hypotheses: any[]` state that holds the
  FULL ranked ledger (normalized the same way as the existing single
  `hypothesis`), alongside the existing single top-hypothesis value for
  backward compatibility with other consumers.
- `EvidenceModal.tsx` — new `HypothesisLedger` component: renders every
  competing hypothesis (only shown when there are 2+, i.e. real ledger
  data exists) with its rank, statement, confidence percentage, and
  supporting/contradicting evidence counts. New `AuthorityBadge`
  component: renders each evidence item's `authority` field
  (AUTHORITATIVE/HIGH/MEDIUM/LOW) as a color-coded badge with a distinct
  icon per level, right next to the existing evidence-type label.
- `Dashboard.tsx` — threads `hypotheses` from the hook through to
  `EvidenceModal`.

**Verified:**
1. `npm run build` (`tsc -b && vite build`) passes cleanly with zero
   TypeScript errors after fixing a `JSX.Element` namespace issue
   (replaced with `ReactNode` from `'react'`).
2. Rebuilt and redeployed the `frontend` container; confirmed `curl` to
   `http://localhost:80/` returns `200`.

## Phase 4+ — Deferred (see IMPLEMENTATION_PLAN_FROM_GPT_SPEC.md rationale)

Multi-tenancy, SSO/SCIM, customer-side connector runtimes, a dedicated
graph database, event broker, ChatOps, and a new production web app are
explicitly deferred until there is a second real tenant/customer —
building them now against a single-deployment codebase would be premature
engineering per the existing scoping document.
