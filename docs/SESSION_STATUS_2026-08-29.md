# NemoGuard Development Session Status — 2026-08-29

This file summarizes the current implementation status against
`docs/NemoGuard_Internal_Org_Next_Steps_for_Coding_Agent_2026-08-27_v2_Commander_Live.md`
for handoff to another agent/session.

## Environment state

- Working tree: clean, all work committed to branch `enterprise-hardening`.
- All docker-compose services healthy and running (`nemoguard-api` rebuilt
  with the latest code as of this session).
- No pending migrations; latest migration applied: `016_model_evaluation.sql`.

## Commits made this session (newest first)

```
0cc4623 WP-ORG-005 (partial): False Resolution Rate safety-net audit
28470ce WP-ORG-004: Model Evaluation Service
ec372eb WP-ORG-006: historical incident recurrence detection
daf7d7c WP-ORG-003: Incident Memory (governed memory layer)
dca63ef Commander Live: fix zero user feedback during/after chat-triggered reinvestigation
9fe8c00 Commander Live: fix "reinvestigate" doing nothing + add conversation memory
```

(Prior session commits below this point: `fb53310` Teams Incident
Communications, `e1f0c73`/`05db0ea`/`1517678`/`431aecb` Commander Pulse +
Commander Live, `84603af` Historical Incident Replay.)

## Roadmap status vs. the priority order in the spec (§2 "New priority order")

### P0 — Organizational intelligence and real-time collaboration

| # | Item | Status |
|---|------|--------|
| 1 | Historical Incident Replay | ✅ Done, live-LLM validated |
| 2 | Commander Live (Ask/Guide/Add Fact) | ✅ Done, live-LLM validated. Includes 2 bug fixes this session: reinvestigation was classified but never executed (fixed), and zero chat feedback during/after reinvestigation (fixed) |
| 3 | Commander Pulse | ✅ Done |
| 4 | Teams Incident Communications | ✅ Done (Phase A outbound webhook), live-tested against a real webhook endpoint |
| 5 | Incident Memory | ✅ Done. Draft generation on resolution, human review lifecycle (DRAFT→APPROVED/REJECTED/REDACTED/EXPIRED), similarity retrieval injected into RCA via existing `feedback_context` mechanism. Live-validated end to end |
| 6 | Model Evaluation Service | ✅ Done. Fixed root gap: `model_name` was persisted on replay rows since WP-ORG-001 but never actually used — wired real `model_override` support through every agent (RCA/Dependency/Runbook/GroundingCritic) + `LangGraphInvestigator`. Built run/scorecard service. Live-validated: Nemotron Super vs Ultra on a real historical incident — both 100% RCA accuracy, Super 132.8s avg latency vs Ultra 351.3s (real, measured difference) |
| 7 | Scenario Catalog → scored benchmark | 🟡 **Partial**. Only "False Resolution Rate" implemented (`src/domain/evaluation/false_resolution.py` + `GET /api/v2/admin/false-resolutions`) — live-validated with manufactured true-positive/true-negative test incidents. **NOT done**: RCA Top-1/Top-3, correlation correctness, alert compression, evidence coverage, blast radius recall, safe/unsafe action rate, verification accuracy — these require live-triggering the full 30-scenario LocalStack catalog (`scripts/run_scenario_catalog_30.py`), a multi-hour undertaking not attempted this session. Also not done: growing the catalog toward 50+ cases (terminal recurrence, verification failures, model timeout, invalid structured output, tool unavailable, conflicting evidence, no runbook, invalid HMAC, replay attack, cross-environment access, viewer execution attempt, stale plan hash, plan changed after approval, prompt injection in logs) |
| 8 | Fix terminal-incident correlation | ✅ Done. Terminal-exclusion from active-correlation candidates was already correct in the codebase (verified, not newly broken). Added the missing half: historical recurrence DETECTION + LINKING when a new incident is created that resembles a prior terminal incident's root cause (`incident_recurrence` table, `_detect_and_link_recurrence()`, `GET /api/v2/incidents/{id}/recurrences`). Live-validated with a 100% keyword-match test case |

### P1 — Organizational context and data-depth advantage — **NOT STARTED**
- Internal operations catalog (WP-ORG-007)
- Data lineage and business dependency model (WP-ORG-008)
- Data Integrity Engine (WP-ORG-009)
- Recovery Safety Profiles (WP-ORG-010)
- Runbook knowledge layer (WP-ORG-011)
- Change/deployment history integration (WP-ORG-012)
- Ownership and SLA context (part of WP-ORG-007/008)

### P2 — Real-world validation — **NOT STARTED**
- Shadow-mode pilot (WP-ORG-013)
- Human-vs-NemoGuard comparison capture (WP-ORG-014)
- Commander intervention analytics
- Confidence calibration (WP-ORG-015)
- Model comparison harness (partially covered by WP-ORG-004's Model
  Evaluation Service, but the "pilot-driven" comparison capture itself is
  not built)
- Pilot-driven tool/capability expansion (WP-ORG-020)

### P3 — Enterprise hardening — **NOT STARTED**
- Production-like Temporal (WP-ORG-016)
- Operationalize OpenTelemetry (WP-ORG-017)
- Audit/evidence package (this actually may partially exist —
  `GET /api/v2/incidents/{id}/evidence-package` already exists from a
  prior session; not verified against this spec item's exact requirements)
- Runbook governance
- Internal administration
- Harden Teams integration with an org-approved Teams app/bot (currently
  only webhook-based, Phase A)

### P4 — Optional later work — **NOT STARTED**
- Fine-tuning or distillation (WP-ORG-019)
- More autonomous low-risk actions
- Broader platform integrations
- PagerDuty/ServiceNow integration
- SaaS-oriented capabilities

## New files created this session

```
src/domain/memory/__init__.py
src/domain/memory/signature.py
src/domain/memory/memory_engine.py
src/domain/evaluation/__init__.py
src/domain/evaluation/evaluation_engine.py
src/domain/evaluation/false_resolution.py
migrations/014_incident_memory.sql
migrations/015_incident_recurrence.sql
migrations/016_model_evaluation.sql
```

## Key files modified this session

```
src/domain/orchestrator.py         (+297 lines: memory draft/retrieval, recurrence detection, reinvestigation fixes)
src/domain/commander/conversation.py (reinvestigation trigger + chat status messages)
src/domain/agents/commander_live_agent.py (conversation history support)
src/domain/agents/rca_agent.py     (model_override param)
src/domain/agents/dependency_agent.py (model_override param)
src/domain/agents/runbook_agent.py (model_override param)
src/domain/agents/langgraph_investigator.py (model_override threading)
src/domain/replay/replay_engine.py (actually uses model_override now)
src/api/main.py                    (~15 new endpoints across memory/recurrence/eval/false-resolution)
```

## Validation methodology used throughout

Every feature above was validated against the actually-running docker
stack (real Postgres, real NVIDIA Nemotron LLM calls where applicable),
using isolated test data that was created, exercised through the real API
endpoints, verified against expected output, and then cleaned up — not
just written and assumed correct. No feature was committed without a live
round-trip test.

## Suggested next steps (in priority order per the spec)

1. Finish WP-ORG-005: run `scripts/run_scenario_catalog_30.py` live (or a
   representative subset) and compute the remaining scored-benchmark
   metrics (RCA Top-1/3, correlation correctness, alert compression,
   blast radius recall, safe/unsafe action rate) against real results.
2. Grow the scenario catalog toward 50+ cases per the spec's listed gap
   categories (terminal recurrence, verification failures, model
   timeout, invalid structured output, etc.).
3. Begin P1: Internal Operations Catalog (WP-ORG-007) — a deterministic
   model of business capability → data product → pipeline → job →
   dataset → infrastructure, sourced from the existing CMDB.
