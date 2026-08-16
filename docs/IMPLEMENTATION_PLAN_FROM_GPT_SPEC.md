# Implementation Plan — Distilled from the GPT "Real-World Support Engineer" Spec

## How to read this document

The attached spec (`nemoguard_real_world_support_engineer_build_spec.md`) is a
genuinely good **enterprise SaaS platform architecture** — the agent design,
capability-gateway concept, plan-hash/approval-integrity model, and
verification/rollback discipline are all sound and worth adopting. But it is
written at the scope of a funded platform team (multi-tenancy, SSO/SCIM,
customer-side connector runtimes, a new production web app, dedicated
policy-engine service, graph database, event broker, analytics warehouse,
etc.) — roughly 6-12 months of a multi-person team's work.

**NemoGuard today is a single-tenant demo/hackathon deployment** (one
Postgres instance, one docker-compose stack, one team). Most of Sections
17-23 (multi-tenancy, connector SDK, ChatOps, admin console, SSO) and
Section 20 (deployment models) do not apply yet and would be premature
engineering. Building them now would slow down the thing that actually
matters: **making the agent's diagnosis-to-recovery loop real, safe, and
verifiable** — which is exactly what Sections 12-14 and the "Immediate next
actions" (§39) already describe, and which maps directly onto code we
already have (LocalStack lab, `write_tools.py`, `agent_tools.py`,
`langgraph_investigator.py`).

This plan extracts **only the parts of the spec that are (a) high-leverage
for a hackathon/demo-to-pilot codebase and (b) buildable in weeks, not
quarters** — everything else is explicitly deferred with a note on when it
would become relevant (i.e., "when there's a second real customer/tenant").

---

## Part 1 — What we adopt now (high leverage, low cost)

These are direct upgrades to code that already exists. No new
infrastructure services required.

### 1.1 Typed Action Intents + Plan Compiler (replaces free-text plan steps)

**Spec reference:** §12.4, §12.5, §33 (`ActionIntent`, `CompiledAction`,
`RecoveryPlan` Pydantic models)

**Current state:** `action_step.action_type`/`tool_name` are free-text
strings written by the LLM (`orchestrator.py`, `langgraph_investigator.py`).
Execution (`execute_plan` in `orchestrator.py`) doesn't actually look at
`tool_name` at all — it just marks steps `SUCCEEDED`.

**What to build:**
- A small `ActionIntent` Pydantic model (intent_type, target, parameters,
  evidence_ids, expected_effect) that the Runbook Agent / Grounding Critic
  populate instead of a free-text `action`/`tool` string.
- A `capability_id -> callable` registry (start with ~10 entries: the ones
  we already built in `write_tools.py`/`remediate.py` +
  `aws_observability_tools.py`).
- A deterministic `compile_plan(intents: list[ActionIntent]) ->
  CompiledActionPlan` function that resolves each intent to a registered
  capability, validates required args, and computes a plan hash (reuse
  `src/domain/plan_hash.py`, which already exists!).

**Effort:** 2-3 days. This directly fixes the real architectural gap called
out in the spec (§1, gap 6-7) and unblocks everything else below.

### 1.2 Generic execution engine (replaces the two hardcoded lab paths)

**Spec reference:** §12.6, §39 item 9-10

**Current state:** `execute_simulated_action` in `write_tools.py` has two
hardcoded `if job == "order_events" / else` branches. Adding a third
target/table means editing that function by hand again.

**What to build:**
- Extend the capability registry from 1.1 so each capability declares:
  `precondition_check`, `execute`, `verify` as three separate callables.
- One generic `execute_compiled_action(action: CompiledAction) -> ActionResult`
  function that: re-checks preconditions → dry-run if supported → executes →
  records result → calls `verify`.
- Keep the LocalStack-lab-only tools (already built) as the first ~10
  registered capabilities.

**Effort:** 2-3 days, mostly refactoring `write_tools.py` + `remediate.py`
into the new shape rather than new logic.

### 1.3 Independent verification (kill the hardcoded `resolved: True`)

**Spec reference:** §14.1-14.3

**Current state:** Already **partially done** — `verify_incident_recovery`
checks real Postgres + CloudWatch state when `NEMOGUARD_LOCALSTACK_LAB=1`,
but falls back to hardcoded `True` otherwise, and `orchestrator.execute_plan`
inserts two hardcoded "PASSED" `verification_result` rows unconditionally.

**What to build:**
- Remove the hardcoded `verification_result` inserts from
  `orchestrator.execute_plan` entirely; require every compiled action to
  declare a `verify` callable (from 1.2) and use its real result instead.
- Add a `VerificationPolicy` concept only if/when we have >1 verification
  check per action (for now, one `verify()` callable per capability is
  sufficient — don't build the full JSON policy DSL from §14.2 yet).

**Effort:** 1 day (mostly deletion + wiring, since the pieces exist).

### 1.4 Hypothesis ledger with supporting/contradicting evidence

**Spec reference:** §10.1, §33 (`Hypothesis` model)

**Current state:** RCA Agent returns a single `finding` string with a
confidence score; no explicit alternative-hypothesis tracking, no
contradiction tracking.

**What to build:**
- Extend the RCA Agent's JSON schema (already versioned in `rca_agent.py`)
  to return `hypotheses: [{statement, confidence, supporting_evidence_ids,
  contradicting_evidence_ids}]` instead of a single `finding`.
- Persist all candidates in the existing `hypothesis` table (already has a
  `rank_no` column — just need to actually populate >1 row).
- Surface ranked hypotheses in the frontend's `EvidenceModal`/hypothesis
  panel (small UI change).

**Effort:** 2 days (mostly prompt engineering + one new DB write path; the
schema already supports multiple hypotheses).

### 1.5 Change intelligence (deployment/config-change correlation)

**Spec reference:** §8.8

**Current state:** No change-history tool at all.

**What to build (scoped down from the spec's CloudTrail+CI/CD+Git version):**
- One new read-only tool, `list_recent_changes(resource_id, window_minutes)`,
  that queries CloudTrail via LocalStack (`_aws_client("cloudtrail")`) for
  events on a resource in the recent window. This is a ~30-line addition to
  `aws_observability_tools.py`, following the exact same pattern as the 16
  tools already there.
- Add it to the RCA Agent's tool list and prompt ("always check for a
  correlated recent change before concluding root cause").

**Effort:** 1 day.

### 1.6 Real evidence-authority tagging

**Spec reference:** §9.2 (`Authority` enum: AUTHORITATIVE/HIGH/MEDIUM/LOW)

**Current state:** `evidence.evidence_type` exists but has no notion of
"how trustworthy is this source."

**What to build:**
- Add an `authority` column to the `evidence` table (one migration) and
  populate it based on source: LocalStack/AWS tool output = AUTHORITATIVE,
  NemoGuard's own `log_event` = HIGH, runbook/CMDB text = MEDIUM.
- Surface it in the Evidence panel UI (small badge).

**Effort:** half a day.

---

## Part 2 — What we adopt with modification (medium leverage, needs scoping)

### 2.1 Approval integrity binding to plan hash (already exists — extend it)

**Spec reference:** §13.3

**Current state:** `approve_plan` in `api/main.py` **already** validates
`plan_hash` against a freshly recomputed hash and rejects on mismatch (409).
This is already correct per the spec's requirement — no work needed here
beyond what 1.1 adds (the hash will now cover typed `CompiledAction`s
instead of free-text steps, which is strictly better).

### 2.2 Capability certification record (simplify from YAML+approval workflow to a config file)

**Spec reference:** §3.2

**Current state:** No concept of "this action is certified for autonomous
use."

**Scoped-down version:** A single `config/capability_policy.yaml` (extend
the existing `config/action_policy.yaml`, don't build a new subsystem) with
