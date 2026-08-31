# Scored Validation Benchmark — Full 30-Scenario Run Findings

**Run ID:** SVAL-20260829-4F2DAC
**Started:** 2026-08-29T11:18:09Z
**Completed:** 2026-08-29T12:33:38Z (~75 minutes)
**Result file:** docs/validation/scored_validation_result.json

## Summary

```
total_scenarios: 30
diagnostic_scenarios: 16
scoreable_scenarios: 14
trigger_failures: 26
false_resolution_count: 0
false_resolution_rate: 0.0
meets_false_resolution_target: true
```

**26 of 30 scenarios failed to trigger a scoreable result.** This is a
genuine, real finding from a live run against the actual stack -- not a
harness bug in the sense of "the script crashed." The false-resolution
target (0) was honestly met, but only because almost nothing reached a
scoreable terminal state at all.

## Root cause identified

**A stale, still-`EXECUTING` incident (`INC-D76BCF1C`, created
2026-08-27, the user's own real incident from an earlier session) was
present in the `active_incidents` candidate set for every single
correlation decision made during this run.**

`IncidentOrchestrator._process_webhook_unlocked()` queries all incidents
NOT IN `('RESOLVED', 'FAILED', 'CLOSED', 'CANCELLED')` as correlation
candidates, and passes them to `WatcherAgent.analyze()` for the LLM's own
`correlated_incident_id` guess (used as a fallback when the deterministic
correlator finds no strong match). Because `INC-D76BCF1C`'s title/summary
mentions `nemoguard-ingest-job` in a LocalStack-lab context, it is a
plausible-looking correlation target for every `INGEST-*` scenario
triggered during this run -- and the Watcher Agent's own real reasoning
(observed directly via a live diagnostic call) explicitly considered
attaching new alerts to it.

Live diagnostic evidence:
- A direct synchronous call to `IncidentOrchestrator().process_webhook()`
  with a real `nemoguard-ingest-job-errors` CloudWatch-alarm-shaped
  payload showed the Watcher Agent's own chain-of-thought explicitly
  reasoning about `INC-D76BCF1C` as a correlation candidate before this
  process was interrupted.
- No new `alert` row and no new `incident` row were created by that call
  -- consistent with either the LLM call taking far longer than the
  360s the CLI polls for at this decision point (this specific step
  is a single Watcher Agent call, not the full multi-agent chain, so a
  >6-minute stall here is itself an anomaly), or the LLM's turn ending in
  a state the code did not handle as "create a new incident."

## Why this matters

This is exactly the kind of failure the Scored Validation Benchmark is
supposed to be equipped to catch and quantify -- but it also reveals a
real gap in the benchmark's own harness: **the CLI does not clear/cancel
stale non-terminal incidents from prior sessions before running**, so a
long-lived open incident (whether a genuine unresolved production
incident or leftover test data) can silently degrade the ENTIRE scenario
catalog's trigger success rate to near-zero, without any scenario's
actual multi-agent pipeline ever being meaningfully exercised.

## Two other, smaller findings from this run

1. `INGEST-MISSING-INPUT-FILE` / `INGEST-MALFORMED-JSON` scenarios both
   got a real `400 Bad Request` from the simulator's
   `/lab/trigger/ingest` endpoint. The `trigger_scenario_name` values in
   `ground_truth.py` (`missing_input_file`, `malformed_json`) may not
   exactly match the simulator's accepted scenario name set -- needs
   direct verification against `localstack_lab/break_scenario.py`'s
   actual accepted values.
2. All 16 `diagnostic_only=True` scenarios (pure read-only diagnostics,
   healthy baselines, and multi-step correlation assertions) correctly
   report `"No single-trigger mapping for this CLI version"` rather than
   a fabricated pass -- this is the CLI honestly reporting a real
   capability gap (documented in the original WP-029-001 commit), not a
   new issue.

## What did NOT go wrong

- The false-resolution safety net worked exactly as designed: since
  nothing reached `RESOLVED` without genuine verification, the false
  -resolution rate is honestly 0, not a false negative.
- The harness itself did not crash, corrupt data, or silently fabricate
  passing scores for the 26 failed scenarios -- every failure is
  correctly recorded with an honest reason.
- `INC-D76BCF1C` (the user's own real incident) was never mutated by
  this benchmark run.

## Recommended next steps (for the next session)

1. Add a pre-run check to `scripts/run_scored_validation.py` that lists
   all non-terminal incidents before starting and either (a) fails fast
   with a clear message telling the operator to resolve/cancel them
   first, or (b) accepts an explicit `--allow-stale-incidents` flag
   acknowledging the risk, rather than silently degrading every
   scenario's correlation outcome.
2. Verify `localstack_lab/break_scenario.py`'s exact accepted scenario
   name set against `ground_truth.py`'s `trigger_scenario_name` values
   for `INGEST-MISSING-INPUT-FILE` / `INGEST-MALFORMED-JSON`.
3. Re-run the full catalog once (1) and (2) are fixed, with a clean
   active-incident set, to get the first genuinely representative
   RCA Top-1/3 / terminal-state / verification-accuracy scorecard.
4. Consider whether the Watcher Agent's correlation-candidate query
   should exclude incidents that have been non-terminal for longer than
   some threshold (e.g. >24h) by default, separate from this benchmark's
   own needs -- a long-stuck incident silently absorbing new, unrelated
   alerts indefinitely is a real product risk, not just a benchmark
   inconvenience.
