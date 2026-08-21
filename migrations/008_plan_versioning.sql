-- Plan versioning support for the feedback/rejection flow (spec §10.2/10.3,
-- docs/NemoGuard_Enterprise_Hardening_and_Productization_Build_Plan.md
-- Priority 6).
--
-- Previously, rejecting a plan patched the SAME action_plan row in place
-- (UPDATE ... SET rationale=..., DELETE FROM action_step WHERE
-- action_plan_id=..., re-INSERT new steps) -- destroying the original
-- rejected plan's content and losing the human's feedback as a distinct,
-- auditable artifact. Every plan revision must now be a NEW immutable
-- action_plan row, linked back to its predecessor via parent_plan_id, with
-- the specific feedback that triggered the revision recorded in
-- plan_feedback and referenced via feedback_reference.

ALTER TABLE action_plan ADD COLUMN IF NOT EXISTS parent_plan_id VARCHAR;
ALTER TABLE action_plan ADD COLUMN IF NOT EXISTS feedback_reference VARCHAR;
ALTER TABLE action_plan ADD COLUMN IF NOT EXISTS created_by_agent_run_id VARCHAR;

-- Distinct, append-only record of human feedback that triggered a plan
-- revision. Previously human rejection feedback was only ever passed as a
-- raw string into an LLM prompt and then discarded -- never persisted as
-- its own auditable record tied to the specific plan it was feedback on.
CREATE TABLE IF NOT EXISTS plan_feedback (
    plan_feedback_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    rejected_plan_id VARCHAR NOT NULL,
    feedback_text VARCHAR NOT NULL,
    submitted_by VARCHAR NOT NULL,
    submitted_at VARCHAR NOT NULL,
    resulting_plan_id VARCHAR,
    FOREIGN KEY(incident_id) REFERENCES incident(incident_id),
    FOREIGN KEY(rejected_plan_id) REFERENCES action_plan(action_plan_id)
);

CREATE INDEX IF NOT EXISTS idx_plan_feedback_incident ON plan_feedback(incident_id);
CREATE INDEX IF NOT EXISTS idx_action_plan_parent ON action_plan(parent_plan_id);
