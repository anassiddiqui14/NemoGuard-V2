-- 006_evidence_authority.sql
--
-- Phase 2 of the enterprise build (see docs/ENTERPRISE_BUILD_PROGRESS.md):
-- real evidence-authority tagging (spec §9.2 Authority enum:
-- AUTHORITATIVE/HIGH/MEDIUM/LOW). Previously `evidence.evidence_type` had
-- no notion of "how trustworthy is this source" -- a raw AWS CloudWatch
-- log line and a static runbook description were treated identically by
-- the UI and by any confidence calculation. This lets the Grounding
-- Critic and the operator-facing evidence panel actually weight sources.

ALTER TABLE evidence
    ADD COLUMN IF NOT EXISTS authority VARCHAR NOT NULL DEFAULT 'MEDIUM';

-- Backfill authority for existing rows based on source_system, matching
-- the classification used by src/domain/evidence_authority.py:
--   AUTHORITATIVE: real AWS/LocalStack tool output (CloudWatch, S3, Lambda, etc.)
--   HIGH: NemoGuard's own log_event table (query_logs)
--   MEDIUM: runbook/CMDB derived text (the default, already applied above)
UPDATE evidence SET authority = 'AUTHORITATIVE'
    WHERE source_system IN ('AWS_CLOUDWATCH', 'AWS_S3', 'AWS_LAMBDA', 'AWS_STEPFUNCTIONS', 'AWS_SQS', 'AWS_SNS', 'AWS_RDS', 'AWS_ECS', 'AWS_IAM', 'AWS_SECRETSMANAGER', 'AWS_EC2', 'LocalStack');
UPDATE evidence SET authority = 'HIGH'
    WHERE source_system IN ('log_event', 'Log', 'System') AND authority = 'MEDIUM';

CREATE INDEX IF NOT EXISTS idx_evidence_authority ON evidence(authority);
