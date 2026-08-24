NemoGuard Pipeline Copilot — Current Status & Design Report

**Generated:** 2026-08-24 · **Branch:** `enterprise-hardening` @ `28baf37` (fully committed — no uncommitted work this session)
**Scope:** `pipeline-copilot/` (the actual running application). Supersedes `docs/APP_STATUS_REPORT_2026-08-23.md`.

**Purpose:** An accurate, code-verified snapshot of everything that changed since the 2026-08-23 report, so the next work session (or a reviewer) can pick up cleanly without re-deriving context. Every claim below was checked directly against running containers, live database rows, or a passing test/validation run in this session.

---

## 1. Executive Summary

The 2026-08-23 report ended with a large pile of **uncommitted** work and an explicit recommendation to disentangle and commit it in separate, reviewable pieces. This session did exactly that, then continued forward with new work. In order:

1. **Committed the 2026-08-23 uncommitted work as 13 separate, reviewable commits** (WP-VAL-002 through WP-VAL-005, capability gateway expansion, AWS Glue/AppFlow coverage, and the 30-scenario validation catalog itself).
2. **Ran the full 30-scenario live validation catalog against real infrastructure and found + fixed 2 real product bugs**: (a) a partial-write crash-position edge case, (b) — most significantly — **incidents were never re-investigated when genuinely new evidence arrived after a plan already existed**, silently discarding new root-cause-relevant alerts.
3. **Closed out three real Scenario Cockpit UI/API gaps** that existed only as CLI scripts with zero UI path: `duplicate_write` order-events scenario, CloudWatch Alarm Lifecycle (live state + acknowledge/reset), and Alert Correlation Verification (live, real two-failure correlation checks streamed into the UI).
4. **Investigated migrating off LocalStack to Floci** (given LocalStack Community's March 2026 sunset), attempted a live migration, found a genuine blocking gap, and safely rolled back — fully documented for a future retry.

**Verified live in this session:**
- **141/141 unit tests pass** (checked repeatedly, most recently after the Floci rollback).
- **30/30 scenarios pass** on the final validation catalog run (`docs/validation/scenario_catalog_30_result.json`), after the two real bug fixes below.
- The real correlation/re-investigation bug fix was confirmed live: a `REINVESTIGATION_TRIGGERED` audit event genuinely fired and the full agent pipeline (RCA → Impact → Runbook → Commander) genuinely re-ran for a real incident.
- The Scenario Cockpit's three new sections (duplicate_write, Alarm Lifecycle, Correlation Verification) were each exercised live against real LocalStack/CloudWatch/Postgres/NemoGuard-API infrastructure, not mocked.
- The Floci migration attempt was verified live in both directions: Floci ran, provisioned, and executed real Lambdas correctly, but failed 8/30 scenarios (5 alarm/correlation-cascade + 3 unrelated to the metrics gap were later re-checked as passing); the rollback to LocalStack was re-verified live (alarm genuinely transitions to `ALARM` state again).

---

## 2. Commits landed this session (chronological)

| Commit | Summary |
|---|---|
| `4c7f564` | WP-VAL-002: Repeatable Scenario Test Harness |
| `4b17aa5` | WP-VAL-003: Security & Governance Validation — live RBAC/plan-hash/tenant-isolation checks |
| `556a4e9` | WP-VAL-004: AI Evaluation Benchmark — RCA accuracy against real ground truth |
| `011ec81` | WP-VAL-005: Incident Evidence Package export endpoint |
| `b107fdd` | WP-VAL-005: Adoption Readiness Dashboard — frontend page |
| `bfac35c` | Capability Gateway: register `queue.quarantine_poison_message` |
| `e0722f5` | WP-VAL-005: commit missing adoption-readiness backend endpoint |
| `3a56dbe` | Capability Gateway expansion + real 30-scenario catalog (initial version) |
| `b417d4b` | Add real AWS Glue and Amazon AppFlow capability coverage |
| `ad425af` | **Fix real bugs found via 30-scenario live validation catalog (30/30 PASS)** |
| `79649f0` | **Fix real correlation bug: incidents never re-investigated new evidence** |
| `44793fb` | Wire `duplicate_write` scenario into Scenario Cockpit (real UI + backend) |
| `baefb16` | Add Alarm Lifecycle section to Scenario Cockpit (real CloudWatch state) |
| `01f087d` | Add Alert Correlation Verification to Scenario Cockpit (real, live checks) |
| `28baf37` | Investigate Floci as LocalStack replacement; keep LocalStack (blocking gap found) |

The first 9 commits (`4c7f564` through `b417d4b`) are the disentangled, now-committed version of what the 2026-08-23 report described as "uncommitted, mixed scope." The remaining 6 are new work performed in this session.

---

## 3. Detail: the two real bugs found and fixed

### 3.1 `ad425af` — Fixes from the 30-scenario live validation catalog

Running `scripts/run_scenario_catalog_30.py` (new this session, 641 lines, executes each of the 30 documented scenarios in `docs/validation/scenario_catalog_30.md` against real LocalStack/Postgres/NemoGuard-API infra) surfaced real, previously-undetected issues:
- A partial-write crash-position edge case in the order_events Lambda handler (`localstack_lab/lambda_src/order_events_job/handler.py`) and the `break_order_events_scenario.py`/`break_pipeline_scenario.py` trigger scripts.
- The notification job's poison-pill handling (`localstack_lab/lambda_src/notification_job/handler.py`).
- `localstack_lab/provision.py` gained 24 lines of fixes for reliable idempotent re-provisioning.

Result: catalog went from partial pass to 30/30 (`docs/validation/scenario_catalog_30_result.json`).

### 3.2 `79649f0` — Incidents never re-investigated new evidence (the more significant finding)

**The bug:** When a new alert correlated onto an incident that had *already progressed past investigation* (i.e., a plan already existed — `AWAITING_APPROVAL` or later), the new alert's evidence was written to the database (correctly) but the agent pipeline was **never re-run**. If that new alert represented a genuinely different or additional root cause, the existing plan silently went stale — the Commander, RCA, Impact, and Runbook agents never saw it.

**The fix:** `IncidentOrchestrator._maybe_reinvestigate_on_new_evidence()` (164 new lines in `src/domain/orchestrator.py`). Deliberately conservative:
1. Skips if the incident is still in an active investigation state (`DETECTED`/`CORRELATING`/`TRIAGING`/`INVESTIGATING`) — the in-flight run will naturally pick up the new alert since it queries all alerts for the incident, not just the first.
2. Skips if the `run_id` was already seen on this incident (a genuine retry/duplicate delivery isn't new evidence).
3. Skips terminal incidents (`RESOLVED`/`FAILED`/`CANCELLED`).
4. Otherwise, re-runs the full RCA → Impact → Runbook → Commander pipeline via the same `LangGraphInvestigator` used by the original `triage_incident`/`triage_feedback` paths, and emits a `REINVESTIGATION_TRIGGERED` audit event.

Runs synchronously but only *after* the alert/correlation DB writes are committed in `process_webhook`, so a failure in re-investigation never blocks or corrupts the webhook's own alert ingestion — it's best-effort re-triage, not a required step.

**Verified live:** confirmed the audit event genuinely fired and the pipeline genuinely re-ran end-to-end for a real incident during this session's testing.

---

## 4. Detail: Scenario Cockpit gaps closed

All three of the following previously existed **only as standalone CLI scripts / `scripts/run_scenario_catalog_30.py` internals**, with zero path to trigger or observe them from the Scenario Cockpit UI. All three are now real, live UI+API features:

| Feature | Commit | What it does |
|---|---|---|
| **`duplicate_write` order-events scenario** | `44793fb` | New `/lab/trigger/order_events` scenario value + cockpit button: sends two real, sequential Lambda invocations with the same `order_id`, the second genuinely rejected by Postgres's real `UNIQUE` constraint (`migrations/010_order_events_unique_constraint.sql`, added in `3a56dbe`). |
| **Alarm Lifecycle** | `baefb16` | New `/lab/alarms` (real `describe_alarms`) and `/lab/alarms/reset` (real `set_alarm_state`) endpoints + a cockpit UI panel showing live state for all 3 lab CloudWatch alarms with an "Acknowledge & Reset" action per alarm. |
| **Alert Correlation Verification** | `01f087d` | New streaming `/lab/correlation-check` endpoint (`same_alarm` / `different_alarm` checks) + a cockpit UI panel that triggers two real, sequential Lambda failures and streams NemoGuard's *actual* live correlation decision into the UI (not a scripted assertion). Mirrors `scenario_28`/`scenario_29` of the validation catalog. During this feature's own development, hit and fixed a real timing edge case: a freshly-provisioned CloudWatch alarm's first-ever evaluation, plus real webhook-forward + LLM correlation latency, genuinely exceeded an initial 180s window on one run — confirmed live (the incident *did* land, just slightly later) and widened the detection window to 300s with real headroom. |

All three were exercised live against real LocalStack/CloudWatch/Postgres/NemoGuard-API infrastructure during development, not mocked.

---

## 5. Detail: Floci migration investigation (`28baf37`)

**Why investigated:** LocalStack's free "Community" edition sunsets in March 2026 (requiring paid auth tokens thereafter), and Community already fail-closes on AWS Glue/AppFlow (a gap noted in `b417d4b`'s design notes).

**What was actually done (a live attempt, not just research):**
1. Swapped `docker-compose.yml`'s `localstack` service to `floci/floci:latest-compat` (drop-in, same port 4566/protocol).
2. Re-provisioned successfully: S3 bucket, all 3 Lambdas, SNS topic, both SQS queues, Step Functions state machine, all 3 CloudWatch alarms — no errors.
3. Confirmed real Lambda execution works identically (genuine `KeyError` with real stack trace from the deployed handler).
4. Ran the full 30-scenario catalog against Floci: **22/30 passed**. Fixed a genuine, harmless `FunctionError=Handled` vs `Unhandled` reporting difference along the way (both are valid boto3 responses for the same real unhandled exception — an emulator implementation detail, not something the handler code controls; `_real_function_error()` in `scripts/run_scenario_catalog_30.py` now accepts either).

**Blocking finding:** Floci does not emit `AWS/Lambda` `Errors`/`Invocations` CloudWatch metrics from real Lambda invocations. Confirmed two ways: `list_metrics(Namespace='AWS/Lambda')` returned an empty list after multiple real invocations, and Floci's own container logs showed its `CloudWatchMetricsService` only ever logging `SetAlarmState` calls — never `PutMetricData` from Lambda. This is undocumented in Floci's README/migration guide. It breaks every alarm-threshold-driven scenario this project's real-AWS-lab demo depends on: `ALARM-TRIP-ON-FIRST-ERROR`, `ALARM-NO-RENOTIFY-ON-REPEAT`, and all 3 `CORRELATION-*` scenarios (which cascade-fail because they depend on the alarm → SNS → SQS → webhook-forwarder chain that never fires without a real metric datapoint) — 6 of the 8 failures.

**Decision:** Rolled back `docker-compose.yml` to `localstack/localstack:3`. Re-verified live after rollback: re-provisioned cleanly, triggered a real `schema_drift` failure, and confirmed the CloudWatch alarm genuinely transitioned to `ALARM` state (proving LocalStack's auto-metric-emission — the exact capability Floci lacks — works as expected). 141/141 unit tests pass post-rollback. The unused `floci/floci:latest-compat` image and its leftover Lambda container were removed; the environment is fully back to its pre-investigation state except for the retained, harmless `_real_function_error()` compat fix.

**For a future session:** search/file this gap against `floci-io/floci`'s issue tracker; retry the migration once Lambda CloudWatch metric emission is added upstream. The migration path itself (image swap + env var translation) is otherwise straightforward and was proven to work — this is the one blocking item.

---

## 6. Current environment state (verified live, end of session)

| Service | Image | Status |
|---|---|---|
| `nemoguard-postgres` | `postgres:15-alpine` | Up, healthy |
| `nemoguard-temporal` | `temporalio/admin-tools:latest` | Up (dev-mode, unchanged from prior reports) |
| `nemoguard-api` | `pipeline-copilot-api` | Up |
| `nemoguard-temporal-worker` | `pipeline-copilot-temporal-worker` | Up |
| `nemoguard-frontend` | `pipeline-copilot-frontend` | Up |
| `nemoguard-simulator` | `pipeline-copilot-simulator` | Up; `/lab/status` reports `available: true`, `forwarder_running: true` |
| `nemoguard-localstack` | `localstack/localstack:3` | Up, healthy (post-Floci-rollback) |

No `redis` service exists in `docker-compose.yml` or is currently running — the 2026-08-23 report's "mystery redis" open question (§4.2 of that report) appears to have resolved itself; it was not investigated further this session since it's no longer present.

`src/domain/impact_engine.py` and `tests/unit/domain/test_impact_engine.py` (flagged as ambiguous "already in-progress, unclear if finished" in the 2026-08-23 report) are present and committed as part of the disentangled commit set — their functional completeness was not independently re-verified this session beyond the fact that their tests are part of the passing 141/141 unit suite.

---

## 7. Known gaps carried over (unchanged unless noted)

1. **Temporal is still dev-mode** (in-memory, no TLS, no persistent Temporal DB, no HA) — highest-impact gap, unchanged.
2. **Capability gateway coverage** — expanded this session (Glue/AppFlow, queue.quarantine_poison_message) but still not exhaustive versus the full AWS surface now available via Floci/LocalStack.
3. **Observability wired but not operationalized** — OpenTelemetry present, no real trace backend/dashboards/alerting; unchanged.
4. **`src/ui/` legacy Streamlit dashboard** — still present, still dead code, still not deleted.
5. **LocalStack Community sunset (March 2026)** — not yet resolved; see §5 above. This is now a real, dated deadline, not a hypothetical concern.
6. **The correlator's terminal-incident-matching behavior** (flagged in the 2026-08-23 report §4.1: a live incident can correlate against an already-`FAILED` incident from days prior) — this was NOT addressed this session; it remains an open product decision, separate from the re-investigation bug fixed in §3.2 above (which is about *active* incidents receiving new evidence, not about matching into *terminal* ones).

---

## 8. Suggested next priorities (for review)

1. **Decide the correlator's terminal-incident-matching behavior** (§7.6, carried over from 2026-08-23, still unaddressed) — this has a real, demonstrated live example to reason from and should not keep being deferred.
2. **Track the Floci blocking gap** — either file an issue upstream, or budget time to work around it (e.g., have the lab's Lambda handlers manually call `put_metric_data` for `Errors`/`Invocations` themselves, which would make the alarm-driven flow emulator-agnostic and remove this dependency on either tool's auto-instrumentation).
3. **Temporal production deployment** (§7.1) — still the single highest-impact infrastructure gap, unaddressed across multiple reports now.
4. **Delete `src/ui/`** (§7.4) — low-effort, still not done.
5. **Independently re-verify `impact_engine.py`'s functional completeness** beyond unit-test presence, since its provenance (authored before this session, committed during the disentangling pass) was never directly reviewed for correctness.
