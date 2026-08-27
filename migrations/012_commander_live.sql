-- WP-ORG-002: Commander Live, Commander Pulse & incident conversation.
--
-- See docs/NemoGuard_Internal_Org_Next_Steps_for_Coding_Agent_2026-08-27_v2_Commander_Live.md
-- section 4. Reuses the existing audit_event table as the durable source
-- of operational truth (no second, potentially-divergent event system);
-- commander_status_update is a PROJECTION derived from audit_event rows
-- (via src/domain/commander/status_projector.py), and
-- source_audit_event_id has a UNIQUE constraint to make that projection
-- idempotent.
--
-- All CREATE TABLE statements use IF NOT EXISTS / ADD COLUMN IF NOT EXISTS
-- so this migration is safe to re-run on every API startup (see
-- src/store/postgres_database.py::apply_pending_migrations).

CREATE TABLE IF NOT EXISTS commander_status_update (
    update_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    source_audit_event_id VARCHAR,
    update_type VARCHAR NOT NULL,
    created_at VARCHAR NOT NULL,
    headline VARCHAR NOT NULL,
    summary VARCHAR,
    severity VARCHAR,
    lifecycle_state VARCHAR,
    evidence_refs_json VARCHAR,
    plan_id VARCHAR,
    visibility VARCHAR NOT NULL DEFAULT 'OPERATOR',
    notify_external INTEGER NOT NULL DEFAULT 0
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'commander_status_update_source_audit_event_id_key'
    ) THEN
        ALTER TABLE commander_status_update
            ADD CONSTRAINT commander_status_update_source_audit_event_id_key UNIQUE (source_audit_event_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_commander_status_incident
    ON commander_status_update(incident_id, created_at);

-- Persistent Commander Live conversation. Each incident has an implicit
-- session (no separate "session" row needed -- messages are simply
-- scoped by incident_id, matching how audit_event/evidence/hypothesis are
-- already scoped in this schema).
CREATE TABLE IF NOT EXISTS incident_message (
    message_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    role VARCHAR NOT NULL,          -- 'OPERATOR' | 'COMMANDER'
    intent VARCHAR,                 -- 'ASK' | 'GUIDE' | 'ADD_FACT' | NULL (Commander replies have no intent)
    content VARCHAR NOT NULL,
    created_by VARCHAR,
    created_at VARCHAR NOT NULL,
    evidence_refs_json VARCHAR,
    guidance_id VARCHAR,            -- set on OPERATOR messages with intent GUIDE/ADD_FACT
    guidance_revision INTEGER
);

CREATE INDEX IF NOT EXISTS idx_incident_message_incident
    ON incident_message(incident_id, created_at);

-- Durable, auditable record of human guidance/facts. Separate from
-- incident_message so guidance can be tracked/invalidated/referenced by
-- id independently of the conversational transcript (e.g. by
-- action_plan.invalidated_by_guidance_id in a future pass).
CREATE TABLE IF NOT EXISTS commander_guidance (
    guidance_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    created_at VARCHAR NOT NULL,
    created_by VARCHAR,
    source_channel VARCHAR NOT NULL DEFAULT 'UI',
    guidance_type VARCHAR NOT NULL,   -- INVESTIGATION_DIRECTION | HYPOTHESIS_FEEDBACK | RECOVERY_CONSTRAINT | EVIDENCE_REQUEST | BUSINESS_CONTEXT | MANUAL_EVIDENCE_REFERENCE
    authority VARCHAR NOT NULL DEFAULT 'HUMAN_OBSERVATION', -- HUMAN_OBSERVATION | HUMAN_CONFIRMED_FACT
    text VARCHAR NOT NULL,
    guidance_revision INTEGER NOT NULL,
    triggered_reinvestigation INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_commander_guidance_incident
    ON commander_guidance(incident_id, created_at);

-- Monotonic per-incident guidance counter. A dedicated single-row-per-incident
-- table (rather than deriving MAX(guidance_revision) from commander_guidance
-- each time) makes the increment atomic under concurrent GUIDE/ADD_FACT
-- submissions.
CREATE TABLE IF NOT EXISTS incident_guidance_revision (
    incident_id VARCHAR PRIMARY KEY,
    current_revision INTEGER NOT NULL DEFAULT 0,
    updated_at VARCHAR NOT NULL
);
