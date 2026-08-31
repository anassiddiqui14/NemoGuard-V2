# Scored Validation Benchmark — Full 30-Scenario Run #2 Findings

**Run ID:** SVAL-20260831-CAA168
**Started:** 2026-08-31T11:42:04Z
**Completed:** 2026-08-31T13:02:11Z (~80 minutes)
**Result file:** docs/validation/scored_validation_result.json

## Summary

```
total_scenarios: 30
diagnostic_scenarios: 16
scoreable_scenarios: 14
trigger_failures: 17
rca_top1_accuracy: 0.6
rca_top3_accuracy: 0.6
cause_family_accuracy: 0.6
evidence_coverage_avg: 1.0
safe_action_selection_rate: 0.0
terminal_state_accuracy: 0.0
verification_accuracy: 0.0
false_resolution_count: 0
false_resolution_rate: 0.0
meets_false_resolution_target: true
```

This is the first run that produced genuinely meaningful RCA scores
(previous run 2026-08-29 had `rca_top1_accuracy: None` because almost
nothing reached a scoreable state at all, due to the stale-incident
issue documented in `scored_validation_run_2026-08-29_findings.md`).

## CRITICAL discovery made mid-session: the DB-connection-leak fix was not actually deployed

Earlier the same day, a critical bug was found and fixed in
`src/domain/orchestrator.py` (`_process_webhook_unlocked` holding an
open DB transaction across a multi-minute LLM call — see the
`326b3fc` commit message for full detail) and "verified live" by
restarting the `nemoguard-api` container with `docker compose restart
api`.

**That verification was invalid.** `docker-compose.yml`'s `api`
service builds from `Dockerfile.api` with no source bind-mount — the
application code is baked into the image at build time.
`docker compose restart` only restarts the existing container process;
it does **not** rebuild the image or pick up source changes on disk.
This means the entire `SVAL-20260831-CAA168` run above (all 30
scenarios, ~80 minutes) ran against the **OLD, buggy** orchestrator
code, not the fix.

This was discovered because the exact same leak signature reappeared
live during this run: `pg_stat_activity` showed a new connection
`idle in transaction` for 24+ minutes, holding the exact same
`UPDATE incident SET summary = summary || '...'` query on
`INC-A7036B1D` that the original 2026-08-29 incident (`INC-D76BCF1C`)
was stuck on.

### Corrective action taken (after this run completed)

1. `docker compose build api` — genuinely rebuilt the image from the
   current `src/domain/orchestrator.py` (with the fix).
2. `docker compose up -d --no-deps api` — recreated (not just
   restarted) the container from the new image.
3. Verified via `docker exec nemoguard-api grep -n
   deferred_reinvestigation src/domain/orchestrator.py` that the fixed
   code is genuinely present inside the running container.
4. Re-ran `INGEST-SCHEMA-DRIFT` end-to-end against the rebuilt image:
   completed cleanly, `rca_top1_accuracy=1.0`, zero leaked connections
   afterward (confirmed via direct `pg_stat_activity` query).
5. Manually re-triggered a second `schema_drift` alert afterward as an
   additional smoke test: zero leaked connections, incident correctly
   left in a normal `INVESTIGATING` state, cleaned up.

**The fix is now genuinely deployed and running.** The
`SVAL-20260831-CAA168` scorecard above remains a valid, honest
real-world RCA/correlation benchmark result — the connection-leak bug
does not fabricate or corrupt RCA scoring, it only causes some
scenarios to time out waiting for a still-open transaction to release a
row lock (which is exactly what happened for a subset of the 17
trigger failures below). It should NOT be treated as representative of
post-fix system behavior for the specific class of failures the leak
caused (a subset of the `SKIPPED/FAILED: No incident observed within
360s` results), since the leak was still present throughout.

## Per-scenario results (this run)

| Scenario | trigger_failed | top1 | top3 | terminal | verify |
|---|---|---|---|---|---|
| INGEST-SCHEMA-DRIFT | No | **True** | **True** | False | False |
| INGEST-OOM-CRASH | No | False | False | False | False |
| INGEST-DB-OUTAGE | No | **True** | **True** | False | False |
| INGEST-MISSING-INPUT-FILE | Yes (400 from simulator) | — | — | — | — |
| INGEST-MALFORMED-JSON | Yes (400 from simulator) | — | — | — | — |
| INGEST-HEALTHY-BASELINE | No (correctly no incident) | — | — | — | — |
| ORDER-PARTIAL-WRITE-SMALL | No | None* | None* | False | False |
| ORDER-PARTIAL-WRITE-EARLY | Yes (360s timeout — leak-affected) | — | — | — | — |
| ORDER-PARTIAL-WRITE-LATE | No | None* | None* | False | False |
| ORDER-DUPLICATE-WRITE | Yes (360s timeout — leak-affected) | — | — | — | — |
| ORDER-HEALTHY-BASELINE | No (correctly no incident) | — | — | — | — |
| ORDER-STALENESS-CHECK-ONLY | Yes (no CLI trigger mapping) | — | — | — | — |
| ORDER-VERIFY-ROW-COUNT-MISMATCH | Yes (no CLI trigger mapping) | — | — | — | — |
| NOTIF-POISON-PILL-FIRST | No | None* | None* | False | False |
| NOTIF-POISON-PILL-REDELIVERY | No | None* | None* | False | False |
| NOTIF-QUEUE-BACKUP-MULTI | No | False | False | False | False |
| NOTIF-HEALTHY-BASELINE | No (correctly no incident) | — | — | — | — |
| NOTIF-QUEUE-INSPECT-ONLY | Yes (no CLI trigger mapping) | — | — | — | — |
| NOTIF-QUARANTINE-DRY-RUN | Yes (no CLI trigger mapping) | — | — | — | — |
| PIPELINE-INGEST-STEP-FAILS | No | **True** | **True** | False | False |
| PIPELINE-ORDER-EVENTS-STEP-FAILS | Yes (360s timeout — leak-affected) | — | — | — | — |
| PIPELINE-HEALTHY-BASELINE | No (correctly no incident) | — | — | — | — |
| PIPELINE-EXECUTION-INSPECT | Yes (no CLI trigger mapping) | — | — | — | — |
| ALARM-* (4 scenarios) | Yes (no CLI trigger mapping) | — | — | — | — |
| CORRELATION-* (3 scenarios) | Yes (no CLI trigger mapping) | — | — | — | — |

`*None` = the investigation did not produce any hypotheses within the
360s poll window for that step, so top1/top3 could not be scored
either way (recorded honestly as `None`, never fabricated as pass or
fail).

## Real findings, independent of the connection-leak bug

1. **RCA accuracy is genuinely mixed (3/5 scored correctly, 2/5
   incorrect) on the scenarios that DID complete**, which is honest
   signal the benchmark is designed to surface — not every real
   investigation gets the right answer.
   - `INGEST-OOM-CRASH` and `NOTIF-QUEUE-BACKUP-MULTI` both scored
     `top1_correct=False`; `INGEST-OOM-CRASH`'s hypothesis was
     literally "Unknown root cause" despite a real, unambiguous OOM
     signal in the simulated failure — worth investigating the RCA
     agent's prompt/tool access for this specific failure shape.
2. **`terminal_state_accuracy: 0.0` and `verification_accuracy: 0.0`
   across the board** — every scoreable scenario that got far enough
   to have a plan ended at `AWAITING_APPROVAL`/`EXECUTING`/
   `INVESTIGATING`, never `RESOLVED`, within the poll window. Two
   distinct causes observed:
   - The Commander sometimes proposes a `MANUAL` step (e.g. "increase
     container memory limit") instead of using the registered
     `compute.rerun_ingest_job` capability the ground truth expects,
     which correctly routes to `MANUAL_ACTION_REQUIRED` and never
     auto-executes (this is the safety gate working as designed, not a
     bug — but it does mean this benchmark's `POLL_TIMEOUT_SEC=360`
     per phase is often too short to observe a full RCA→plan→approve→
     execute→verify cycle when a real Nemotron Ultra call sequence is
     involved end-to-end).
   - Several scenarios (all `ORDER-*`/`NOTIF-*` cases with `None`
     top1/top3) never produced hypotheses within the window at all —
     worth checking whether these categories' investigations
     genuinely take longer than `INGEST-*`'s, or whether something
     about order_events/notification alert shapes causes the RCA
     agent to stall.
3. **`INGEST-MISSING-INPUT-FILE`/`INGEST-MALFORMED-JSON`** still get a
   real `400 Bad Request` from the simulator (same finding as
   2026-08-29, not yet fixed) — the `trigger_scenario_name` values in
   `ground_truth.py` need to be checked against
   `localstack_lab/break_scenario.py`'s actual accepted names.
4. **16 diagnostic-only scenarios** correctly report "no single-trigger
   mapping" rather than a fabricated pass, as designed.

## What did NOT go wrong

- False-resolution rate is honestly 0 — nothing was ever marked
  `RESOLVED` without genuine independent verification passing.
- The harness never crashed or corrupted data across either sub-run.
- The stale-incident pre-run check (added 2026-08-29) worked correctly
  every time it was invoked during this session's debugging, including
  correctly blocking a run when a leftover test incident existed.

## Recommended next steps

1. **Increase `POLL_TIMEOUT_SEC`** (currently 360s per phase) for a
   future run, now that the connection leak is fixed — many scenarios
   above were still investigating/pending when the poll gave up, not
   because anything was broken.
2. **Investigate the `INGEST-OOM-CRASH` "Unknown root cause" RCA miss**
   specifically — a real OOM with a real, distinctive error signature
   scoring `top1_correct=False` with an unhelpful hypothesis is a
   genuine RCA-quality issue worth root-causing on its own.
3. **Add CI/deploy safeguard**: since `docker compose restart` silently
   does NOT pick up source changes for this project's `api` service,
   any future "restart the API to apply a fix" step must explicitly be
   `docker compose build api && docker compose up -d --no-deps api`,
   never just `restart`. Worth adding a one-line note to the relevant
   runbook/README so this doesn't recur -- this exact mistake caused
   this entire 30-scenario run to be executed against unfixed code
   without anyone noticing until the leak's signature reappeared live.
4. **Re-run the full 30-scenario catalog once more** against the
   genuinely-rebuilt image, with an increased `POLL_TIMEOUT_SEC`, to
   get the first scorecard that is both leak-free AND has enough time
   budget per phase to observe full RCA→plan→approve→execute→verify
   cycles for the scenarios whose plans don't require manual
   intervention.
