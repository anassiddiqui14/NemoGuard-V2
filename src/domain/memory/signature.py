"""
Deterministic failure signature derivation (WP-ORG-003).

The signature is used for similarity retrieval and must be explainable to
a human reviewer -- it is NOT an embedding. It's a normalized composite of
(cause_type, service/pipeline, a small set of keywords extracted from the
root cause statement) so two incidents with the same underlying failure
mode produce the same or very similar signatures, without requiring any
extra infrastructure (vector DB, embedding model) this deployment doesn't
already have.
"""
import re
from typing import Optional

# Deliberately small and domain-specific rather than a generic NLP
# stopword list -- these are the failure-mode terms that actually
# distinguish one incident type from another in this system's vocabulary.
_SIGNATURE_KEYWORDS = (
    "schema", "column", "rename", "type", "mismatch", "null", "duplicate",
    "timeout", "connection", "unreachable", "dns", "throttl", "rate limit",
    "memory", "oom", "heap", "cpu", "disk", "storage", "partition",
    "permission", "denied", "credential", "auth", "expired", "rotat",
    "stale", "partial write", "poison", "malformed", "corrupt", "missing",
    "deployment", "rollback", "config", "dependency", "downstream", "upstream",
    "queue", "backlog", "lag", "lambda", "ecs", "rds", "s3",
)


def extract_keywords(text: str) -> list:
    lowered = (text or "").lower()
    return sorted({kw for kw in _SIGNATURE_KEYWORDS if kw in lowered})


def derive_failure_signature(
    cause_type: Optional[str], root_cause: str, service: Optional[str] = None,
) -> str:
    """
    Builds a compact, deterministic signature string like:
        SCHEMA_REGRESSION|customer_profile_ingest|column,mismatch,rename

    Two incidents with the same cause_type + service + overlapping
    keyword set will naturally produce identical or near-identical
    signatures, which is exactly what similarity.py's scoring relies on.
    """
    normalized_cause = (cause_type or "OTHER").strip().upper()
    normalized_service = re.sub(r"\s+", "_", (service or "unknown").strip().lower())
    keywords = extract_keywords(root_cause)
    return f"{normalized_cause}|{normalized_service}|{','.join(keywords)}"
