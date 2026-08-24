# NemoGuard Scenario Tests — Full List

30 real-failure scenarios (`docs/validation/scenario_catalog_30.md`), executed live via `scripts/run_scenario_catalog_30.py` against real LocalStack/Postgres/NemoGuard-API infrastructure — no mocking, no scripted-pretend failures. Latest full run: **30/30 PASS** (2026-08-24T06:07:29Z, `docs/validation/scenario_catalog_30_result.json`).

Each scenario is also individually reachable from the **Scenario Cockpit** UI (`/app/scenario-cockpit`) except where noted.

---

## Group 1 — Ingest Job (`nemoguard-ingest-job`, S3 → Lambda → Postgres)

| # | Scenario ID | Real failure | Trigger |
|---|---|---|---|
| 1 | INGEST-SCHEMA-DRIFT | `KeyError: 'last_login_ip'` | Cockpit: Ingest → Schema Drift |
| 2 | INGEST-OOM-CRASH | `MemoryError` (or real runtime OOM-kill) | Cockpit: Ingest → OOM Crash |
| 3 | INGEST-DB-OUTAGE | `psycopg2.OperationalError` (unreachable host) | Cockpit: Ingest → DB Outage |
| 4 | INGEST-MISSING-INPUT-FILE | `NoSuchKey` | `break_scenario.py missing_input_file` |
| 5 | INGEST-MALFORMED-JSON | `json.JSONDecodeError` | `break_scenario.py malformed_json` |
| 6 | INGEST-HEALTHY-BASELINE | none (sanity check) | Cockpit: Ingest → Healthy |

## Group 2 — Order Events Job (`nemoguard-order-events-job`, Glue-style batch)

| # | Scenario ID | Real failure | Trigger |
|---|---|---|---|
| 7 | ORDER-PARTIAL-WRITE-SMALL | `RuntimeError`, crash after 5/10 rows | Cockpit: Order Events → Partial Write Crash |
| 8 | ORDER-PARTIAL-WRITE-EARLY | same, crash after 1/10 rows | catalog-only (parameterized) |
| 9 | ORDER-PARTIAL-WRITE-LATE | same, crash after 9/10 rows | catalog-only (parameterized) |
| 10 | ORDER-DUPLICATE-WRITE | `UniqueViolation` (real `order_events_order_id_unique` constraint) | Cockpit: Order Events → Duplicate Write |
| 11 | ORDER-HEALTHY-BASELINE | none (sanity check) | Cockpit: Order Events → Healthy |
| 12 | ORDER-STALENESS-CHECK-ONLY | n/a — read-only diagnostic | `check_table_staleness()` |
| 13 | ORDER-VERIFY-ROW-COUNT-MISMATCH | n/a — read-only diagnostic | `verify_row_count_matches_expected()` |

## Group 3 — Notification Job (`nemoguard-notification-job`, SQS → Lambda → Postgres)

| # | Scenario ID | Real failure | Trigger |
|---|---|---|---|
| 14 | NOTIF-POISON-PILL-FIRST | `KeyError: 'user_id'` | Cockpit: Notification → Poison Pill |
| 15 | NOTIF-POISON-PILL-REDELIVERY | same, real SQS redelivery backup | re-run poison_pill without clearing queue |
| 16 | NOTIF-QUEUE-BACKUP-MULTI | real accumulating backlog (3-5x poison_pill) | catalog-only |
| 17 | NOTIF-HEALTHY-BASELINE | none (sanity check) | Cockpit: Notification → Healthy |
| 18 | NOTIF-QUEUE-INSPECT-ONLY | n/a — read-only diagnostic | `peek_sqs_messages()` |
| 19 | NOTIF-QUARANTINE-DRY-RUN | n/a — dry-run diagnostic | `queue.quarantine_poison_message(dry_run=True)` |

## Group 4 — Pipeline / Step Functions (`nemoguard-daily-pipeline`)

| # | Scenario ID | Real failure | Trigger |
|---|---|---|---|
| 20 | PIPELINE-INGEST-STEP-FAILS | real `KeyError` inside orchestrated ingest step | Cockpit: Pipeline → Ingest Step Fails |
| 21 | PIPELINE-ORDER-EVENTS-STEP-FAILS | real mid-batch crash inside orchestrated order_events step | Cockpit: Pipeline → Order Events Step Fails |
| 22 | PIPELINE-HEALTHY-BASELINE | none (both steps succeed) | Cockpit: Pipeline → Healthy |
| 23 | PIPELINE-EXECUTION-INSPECT | n/a — read-only diagnostic | `describe_step_function_execution()` |

## Group 5 — Alarm / Observability Lifecycle (cuts across all jobs)

| # | Scenario ID | Real behavior | Trigger |
|---|---|---|---|
| 24 | ALARM-TRIP-ON-FIRST-ERROR | real CloudWatch OK → ALARM transition + real SNS notification | any failure scenario above, first occurrence |
| 25 | ALARM-NO-RENOTIFY-ON-REPEAT | genuinely NO second SNS notification on repeat failure without reset | same alarm-sharing scenario run twice |
| 26 | ALARM-ACKNOWLEDGE-AFTER-FIX | real `set_alarm_state` ALARM → OK with audit reason | Cockpit: Alarm Lifecycle → Acknowledge & Reset |
| 27 | ALARM-STATE-INSPECT-ONLY | n/a — read-only diagnostic | Cockpit: Alarm Lifecycle (live state display) |

## Group 6 — Cross-cutting Alert Correlation

| # | Scenario ID | Real behavior | Trigger |
|---|---|---|---|
| 28 | CORRELATION-SAME-ALARM-NEW-INCIDENT | correlator correctly attaches 2nd alert (different real failure, same alarm) to the SAME open incident | Cockpit: Correlation Verification → Same Alarm |
| 29 | CORRELATION-DIFFERENT-ALARM-NEW-INCIDENT | correlator correctly creates a SEPARATE incident for a different alarm/job | Cockpit: Correlation Verification → Different Alarm |
| 30 | CORRELATION-ALERT-COUNT-GROWTH | incident's alert count genuinely grows on correlation (status stays same, as expected) | catalog-only |

---

## Not tied to a lab scenario (capability coverage, not a triggerable "test")

| Capability | Status |
|---|---|
| `aws.glue.start_job_run` / `stop_job_run` | Real boto3 call; correctly fails closed — AWS Glue is LocalStack PRO-ONLY on the free tier |
| `describe_glue_job_run` / `describe_appflow_flow_execution` | Real boto3 call; honestly reports PRO-ONLY unavailability |

## How to run the full suite

```bash
cd pipeline-copilot
LOCALSTACK_ENDPOINT=http://localhost:4566 \
  .venv/bin/python3 scripts/run_scenario_catalog_30.py --out docs/validation/scenario_catalog_30_result.json

# Run a subset (debugging):
.venv/bin/python3 scripts/run_scenario_catalog_30.py --only scenario_1_schema_drift,scenario_10_duplicate_write
```

Full scenario definitions, exact real exceptions, and the governed remediation capability mapped to each: `docs/validation/scenario_catalog_30.md`.
