-- WP-ORG-004: Model Evaluation Service.
--
-- Lets the SAME incident suite (a set of historical_incident rows, reusing
-- the Historical Incident Replay infrastructure from WP-ORG-001) be run
-- against multiple organization-approved models, with results stored
-- SEPARATELY per model/run and aggregated into a scorecard. Never
-- hardcodes result values -- every number in the scorecard is computed
-- live from real historical_incident_replay_result rows.

CREATE TABLE IF NOT EXISTS model_evaluation_run (
    run_id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    -- JSON list of model_name strings this run compares.
    models_json VARCHAR NOT NULL DEFAULT '[]',
    -- JSON list of historical_incident_id strings in the suite for this run.
    historical_incident_ids_json VARCHAR NOT NULL DEFAULT '[]',
    prompt_version VARCHAR NOT NULL DEFAULT 'v1',
    status VARCHAR NOT NULL DEFAULT 'PENDING',
    created_by VARCHAR,
    created_at VARCHAR NOT NULL,
    completed_at VARCHAR
);

-- Links a model_evaluation_run to the individual replay rows it spawned
-- (one replay per (model, historical_incident) pair), so a scorecard can
-- be recomputed at any time straight from historical_incident_replay(_result)
-- without duplicating any metric.
CREATE TABLE IF NOT EXISTS model_evaluation_replay_link (
    run_id VARCHAR NOT NULL,
    replay_id VARCHAR NOT NULL,
    model_name VARCHAR NOT NULL,
    historical_incident_id VARCHAR NOT NULL,
    PRIMARY KEY (run_id, replay_id),
    CONSTRAINT model_eval_link_run_fk FOREIGN KEY (run_id) REFERENCES model_evaluation_run(run_id),
    CONSTRAINT model_eval_link_replay_fk FOREIGN KEY (replay_id) REFERENCES historical_incident_replay(id)
);

CREATE INDEX IF NOT EXISTS idx_model_eval_link_run ON model_evaluation_replay_link(run_id);
