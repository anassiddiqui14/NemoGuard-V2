-- WP-ORG-003: Incident Memory (governed memory layer).
--
-- See docs/NemoGuard_Internal_Org_Next_Steps_for_Coding_Agent_2026-08-27_v2_Commander_Live.md
-- section 5. Explicitly NOT a model-training mechanism -- this is a
-- structured, queryable, human-reviewable memory record store. Every
-- draft memory is generated deterministically from real, already-persisted
-- incident data (hypothesis/action_plan/verification_result/plan_feedback
-- rows), never fabricated, and NEVER participates in future investigation
-- until a human has explicitly moved it to APPROVED.

CREATE TABLE IF NOT EXISTS incident_memory (
    memory_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    tenant_id VARCHAR NOT NULL DEFAULT 'default_tenant',

    -- Structured failure signature -- what similarity retrieval matches
    -- against. Deliberately simple/deterministic (not an embedding) so
    -- matches are always explainable to a human reviewer.
    failure_signature VARCHAR NOT NULL,
    service VARCHAR,
    pipeline VARCHAR,
    environment VARCHAR,

    root_cause VARCHAR NOT NULL,
    cause_type VARCHAR,
    supporting_evidence_json VARCHAR NOT NULL DEFAULT '[]',
    contradicting_evidence_json VARCHAR NOT NULL DEFAULT '[]',

    successful_recovery VARCHAR,
    failed_recovery_attempts_json VARCHAR NOT NULL DEFAULT '[]',
    runbook_used VARCHAR,
    capabilities_used_json VARCHAR NOT NULL DEFAULT '[]',

    verification_result VARCHAR,
    data_integrity_result VARCHAR,
    human_feedback VARCHAR,

    mttr_seconds REAL,
    tags_json VARCHAR NOT NULL DEFAULT '[]',

    created_at VARCHAR NOT NULL,
    reviewed_by VARCHAR,
    reviewed_at VARCHAR,
    -- DRAFT | REVIEWED | APPROVED | REJECTED | REDACTED | EXPIRED
    memory_status VARCHAR NOT NULL DEFAULT 'DRAFT',
    review_notes VARCHAR
);

CREATE INDEX IF NOT EXISTS idx_incident_memory_status ON incident_memory(memory_status);
CREATE INDEX IF NOT EXISTS idx_incident_memory_tenant ON incident_memory(tenant_id, memory_status);
CREATE INDEX IF NOT EXISTS idx_incident_memory_signature ON incident_memory(failure_signature);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'incident_memory_incident_id_unique'
    ) THEN
        ALTER TABLE incident_memory
            ADD CONSTRAINT incident_memory_incident_id_unique UNIQUE (incident_id);
    END IF;
END $$;

-- Durable audit trail of every memory retrieval actually surfaced to an
-- investigation, so "memory retrieval is visible in the UI" (acceptance
-- criterion) has a real backing record rather than only being visible
-- transiently in an API response.
CREATE TABLE IF NOT EXISTS incident_memory_retrieval (
    retrieval_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    memory_id VARCHAR NOT NULL,
    similarity_score REAL NOT NULL,
    match_reasons_json VARCHAR NOT NULL DEFAULT '[]',
    retrieved_at VARCHAR NOT NULL,
    presented_to_rca INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_memory_retrieval_incident ON incident_memory_retrieval(incident_id, retrieved_at);
