-- WP-ORG-001: Historical Incident Replay
--
-- Lets a past organizational incident be replayed through the SAME
-- multi-agent investigation graph (LangGraphInvestigator) used for live
-- incidents, using only the evidence that was available at the time, with
-- the actual human-confirmed root cause/recovery hidden from the AI until
-- scoring. See docs/NemoGuard_Internal_Org_Next_Steps_for_Coding_Agent_2026-08-27_v2_Commander_Live.md
-- §3 (WP-ORG-001).
--
-- All CREATE TABLE statements use IF NOT EXISTS / ADD COLUMN IF NOT EXISTS
-- so this migration is safe to re-run on every API startup, matching the
-- convention already used by every other migrations/NNN_*.sql file (see
-- src/store/postgres_database.py::apply_pending_migrations).

CREATE TABLE IF NOT EXISTS historical_incident (
    tenant_id VARCHAR DEFAULT 'default_tenant',
    workspace_id VARCHAR,
    environment_id VARCHAR,
    id VARCHAR PRIMARY KEY,
    external_incident_id VARCHAR,
    source_system VARCHAR NOT NULL,
    opened_at VARCHAR NOT NULL,
    resolved_at VARCHAR,
    service VARCHAR,
    pipeline VARCHAR,
    environment VARCHAR,
    severity VARCHAR,
    title VARCHAR NOT NULL,
    created_at VARCHAR NOT NULL,
    created_by VARCHAR
);

-- Point-in-time evidence available DURING the historical incident (alerts,
-- logs, job states, deployment/change history, schema info, topology,
-- runbooks available at the time, ticket metadata). Never contains the
-- final RCA/postmortem/resolution -- that lives exclusively in
-- historical_incident_ground_truth, a separate table the replay pipeline
-- never queries.
CREATE TABLE IF NOT EXISTS historical_incident_snapshot (
    id VARCHAR PRIMARY KEY,
    historical_incident_id VARCHAR NOT NULL,
    snapshot_type VARCHAR NOT NULL,
    snapshot_timestamp VARCHAR NOT NULL,
    source_reference VARCHAR,
    payload_json VARCHAR NOT NULL,
    created_at VARCHAR NOT NULL,
    FOREIGN KEY(historical_incident_id) REFERENCES historical_incident(id)
);

-- Hidden ground truth. Intentionally a separate table (not a column on
-- historical_incident) so it is trivial to prove -- via the schema alone --
-- that the replay execution path (which only ever loads historical_incident
-- + historical_incident_snapshot) has no way to accidentally read this.
CREATE TABLE IF NOT EXISTS historical_incident_ground_truth (
    historical_incident_id VARCHAR PRIMARY KEY,
    root_cause VARCHAR NOT NULL,
    cause_type VARCHAR,
    actual_recovery VARCHAR,
    actual_impacted_assets_json VARCHAR,
    actual_business_impact VARCHAR,
    actual_resolution_time_seconds REAL,
    postmortem_reference VARCHAR,
    created_at VARCHAR NOT NULL,
    FOREIGN KEY(historical_incident_id) REFERENCES historical_incident(id)
);

CREATE TABLE IF NOT EXISTS historical_incident_replay (
    id VARCHAR PRIMARY KEY,
    historical_incident_id VARCHAR NOT NULL,
    model_provider VARCHAR,
    model_name VARCHAR,
    prompt_version VARCHAR,
    started_at VARCHAR,
    completed_at VARCHAR,
    status VARCHAR NOT NULL DEFAULT 'PENDING',
    error_message VARCHAR,
    created_by VARCHAR,
    FOREIGN KEY(historical_incident_id) REFERENCES historical_incident(id)
);

CREATE TABLE IF NOT EXISTS historical_incident_replay_result (
    replay_id VARCHAR PRIMARY KEY,
    top_hypothesis VARCHAR,
    top_hypothesis_cause_type VARCHAR,
    top_hypothesis_score REAL,
    top_3_hypotheses_json VARCHAR,
    selected_runbook VARCHAR,
    recommended_plan_json VARCHAR,
    tool_calls_json VARCHAR,
    evidence_ids_json VARCHAR,
    elapsed_seconds REAL,
    -- Scoring against the hidden ground truth, computed once the replay
    -- completes. top1_correct/top3_correct are booleans stored as 0/1 for
    -- portability with the rest of this schema (see e.g. action_step.
    -- requires_approval using INTEGER 0/1 elsewhere in this codebase).
    top1_correct INTEGER,
    top3_correct INTEGER,
    cause_family_correct INTEGER,
    scored_at VARCHAR,
    FOREIGN KEY(replay_id) REFERENCES historical_incident_replay(id)
);

CREATE INDEX IF NOT EXISTS idx_historical_snapshot_incident ON historical_incident_snapshot(historical_incident_id);
CREATE INDEX IF NOT EXISTS idx_historical_replay_incident ON historical_incident_replay(historical_incident_id);
CREATE INDEX IF NOT EXISTS idx_historical_replay_status ON historical_incident_replay(status);
