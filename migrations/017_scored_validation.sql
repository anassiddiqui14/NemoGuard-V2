-- WP-029-001: Scored Validation Benchmark result persistence.
--
-- Persists every scenario score computed by
-- src/domain/evaluation/scoring.py so results survive across CLI runs,
-- can be compared over time/model/prompt-version, and can back the
-- Adoption Readiness dashboard with REAL (not hardcoded) numbers.

CREATE TABLE IF NOT EXISTS scored_validation_run (
    run_id VARCHAR PRIMARY KEY,
    model_name VARCHAR,
    prompt_version VARCHAR NOT NULL DEFAULT 'v1',
    started_at VARCHAR NOT NULL,
    completed_at VARCHAR,
    total_scenarios INTEGER NOT NULL DEFAULT 0,
    created_by VARCHAR
);

CREATE TABLE IF NOT EXISTS scored_validation_result (
    result_id VARCHAR PRIMARY KEY,
    run_id VARCHAR NOT NULL,
    scenario_id VARCHAR NOT NULL,
    incident_id VARCHAR,
    -- Full ScenarioScore.to_dict() JSON -- the single source of truth;
    -- individual columns below are extracted for fast aggregate queries
    -- but the JSON blob is authoritative.
    score_json VARCHAR NOT NULL,
    top1_correct INTEGER,
    top3_correct INTEGER,
    cause_family_correct INTEGER,
    evidence_coverage REAL,
    safe_action_selected INTEGER,
    unsafe_action_blocked INTEGER,
    terminal_state_correct INTEGER,
    verification_correct INTEGER,
    false_resolution INTEGER,
    elapsed_seconds REAL,
    diagnostic_only INTEGER NOT NULL DEFAULT 0,
    trigger_failed INTEGER NOT NULL DEFAULT 0,
    created_at VARCHAR NOT NULL,
    CONSTRAINT scored_validation_result_run_fk FOREIGN KEY (run_id) REFERENCES scored_validation_run(run_id)
);

CREATE INDEX IF NOT EXISTS idx_scored_validation_result_run ON scored_validation_result(run_id);
CREATE INDEX IF NOT EXISTS idx_scored_validation_result_scenario ON scored_validation_result(scenario_id);
