"""
Deterministic evidence-authority classification (spec §9.2).

Given a source_system string (as already stored on `evidence.source_system`
throughout the codebase), returns one of AUTHORITATIVE / HIGH / MEDIUM / LOW
-- computed in code, never inferred by an LLM. This lets the Grounding
Critic and the operator-facing evidence panel weight sources by how
trustworthy they actually are, instead of treating a raw CloudWatch log
line identically to a static runbook description.
"""
from __future__ import annotations

# Real AWS/LocalStack tool output -- direct observation of actual
# infrastructure state, the highest-trust category.
_AUTHORITATIVE_SOURCES = {
    "AWS_CLOUDWATCH", "AWS_S3", "AWS_LAMBDA", "AWS_STEPFUNCTIONS",
    "AWS_SQS", "AWS_SNS", "AWS_RDS", "AWS_ECS", "AWS_IAM",
    "AWS_SECRETSMANAGER", "AWS_EC2", "LocalStack", "LLM-Tool",
}

# NemoGuard's own recorded application logs -- a real signal, but only as
# complete/accurate as what the job itself chose to write back.
_HIGH_SOURCES = {"log_event", "Log", "System", "LLM-Tool"}

# Runbook/CMDB-derived text, alert payload text -- useful context but not
# a direct observation of current system state.
_MEDIUM_SOURCES = {"Runbook", "CMDB", "Alert", "Datadog", "PagerDuty", "Webhook"}


def classify_authority(source_system: str) -> str:
    if not source_system:
        return "LOW"
    normalized = source_system.strip()
    if normalized in _AUTHORITATIVE_SOURCES or normalized.upper().startswith("AWS_"):
        return "AUTHORITATIVE"
    if normalized in _HIGH_SOURCES:
        return "HIGH"
    if normalized in _MEDIUM_SOURCES:
        return "MEDIUM"
    return "MEDIUM"


AUTHORITY_WEIGHTS = {
    "AUTHORITATIVE": 1.0,
    "HIGH": 0.8,
    "MEDIUM": 0.5,
    "LOW": 0.2,
}


def authority_weight(authority: str) -> float:
    return AUTHORITY_WEIGHTS.get(authority, 0.5)
