-- 005_capability_gateway.sql
--
-- Supports the Governed Capability Gateway (src/capabilities/*), which
-- replaces free-text tool_name execution with typed, registered
-- capabilities that are precondition-checked, executed, and independently
-- verified (see docs/nemoguard_real_world_support_engineer_build_spec.md
-- §12 and docs/IMPLEMENTATION_PLAN_FROM_GPT_SPEC.md Part 1).
--
-- Adds:
--   - action_step.capability_id / capability_version: the resolved
--     capability an action_step is actually bound to (populated by the
--     Plan Compiler at execution time; NULL for steps that predate this
--     migration or were never compiled).
--   - action_plan.compiled_plan_hash: the hash of the COMPILED plan
--     (over resolved capabilities+args), distinct from the legacy
--     plan_hash on `approval` which hashes the free-text plan/step
--     fields (see src/domain/plan_hash.py). Both are kept during the
--     transition; new code should prefer compiled_plan_hash.
--   - action_execution.capability_id / verification_status /
--     verification_details_json: records exactly which capability ran
--     and what its independent verification concluded, instead of the
--     previous hardcoded-PASSED verification_result rows.

ALTER TABLE action_step
    ADD COLUMN IF NOT EXISTS capability_id VARCHAR,
    ADD COLUMN IF NOT EXISTS capability_version VARCHAR;

ALTER TABLE action_plan
    ADD COLUMN IF NOT EXISTS compiled_plan_hash VARCHAR;

ALTER TABLE action_execution
    ADD COLUMN IF NOT EXISTS capability_id VARCHAR,
    ADD COLUMN IF NOT EXISTS verification_status VARCHAR,
    ADD COLUMN IF NOT EXISTS verification_details_json VARCHAR;

CREATE INDEX IF NOT EXISTS idx_action_step_capability ON action_step(capability_id);
CREATE INDEX IF NOT EXISTS idx_action_execution_capability ON action_execution(capability_id);
