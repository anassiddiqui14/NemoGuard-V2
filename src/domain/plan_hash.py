"""
Deterministic content-hashing for ActionPlan + ActionStep records.

Used to bind a human approval decision to the *exact* plan content that was
presented to the approver. If the plan changes (e.g. revised via feedback)
between when it was fetched and when it is approved, the hash will no longer
match and the approval must be rejected (see src/api/main.py::approve_plan).

This replaces the previous placeholder behavior where the frontend sent the
plan's own ID as a fake "hash" (which the backend never validated).
"""
import hashlib
import json
from typing import Any, Dict, List


def _normalize_plan(plan: Dict[str, Any], steps: List[Dict[str, Any]]) -> str:
    plan_fields = {
        "action_plan_id": plan.get("action_plan_id"),
        "incident_id": plan.get("incident_id"),
        "plan_version": plan.get("plan_version"),
        "overall_risk": plan.get("overall_risk"),
        "rationale": plan.get("rationale"),
        "expected_outcome": plan.get("expected_outcome"),
        "rollback_summary": plan.get("rollback_summary"),
    }
    step_fields = [
        {
            "sequence_no": s.get("sequence_no"),
            "action_type": s.get("action_type"),
            "tool_name": s.get("tool_name"),
            "risk_level": s.get("risk_level"),
            "parameters_json": s.get("parameters_json"),
        }
        for s in sorted(steps, key=lambda s: s.get("sequence_no", 0))
    ]
    payload = {"plan": plan_fields, "steps": step_fields}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_plan_hash(plan: Dict[str, Any], steps: List[Dict[str, Any]]) -> str:
    """Returns a stable SHA-256 hex digest of the plan's approval-relevant content."""
    normalized = _normalize_plan(plan, steps)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
