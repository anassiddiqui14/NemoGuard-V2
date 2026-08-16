-- 003_relax_incident_fks.sql
--
-- Real-world usability fix: `incident.primary_run_id` and `incident.primary_job_id`
-- previously had hard FOREIGN KEY constraints requiring a matching row in the
-- `execution` / `job` tables. That assumption holds for our synthetic
-- simulator scenarios (which always fabricate a matching `execution` row
-- before creating an incident), but breaks for real-world incidents that
-- originate from external monitoring alerts (Datadog, PagerDuty, Sentry,
-- etc.) that have no corresponding Airflow/Spark job execution at all.
--
-- Concretely: sending a real, masked Datadog alert through
-- /api/v2/ingest/webhook caused an unhandled 500
-- (psycopg2.errors.ForeignKeyViolation on incident_primary_run_id_fkey)
-- because the alert's run_id has no row in `execution`.
--
-- Fix: drop both FK constraints. The columns remain as informational
-- free-text references (still useful for correlating back to a pipeline
-- run when one genuinely exists), but no longer block incident creation
-- for alerts that don't come from a tracked pipeline job execution.

ALTER TABLE incident DROP CONSTRAINT IF EXISTS incident_primary_run_id_fkey;
ALTER TABLE incident DROP CONSTRAINT IF EXISTS incident_primary_job_id_fkey;
