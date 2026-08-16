"""
Compatibility bridge: maps EXISTING free-text action_step rows (tool_name /
action_type strings already being produced by the RCA/Runbook/Commander
agents' prompts) into typed ActionIntent objects the Plan Compiler can
consume.

This lets the generic execution engine work TODAY against the plans
already being generated, without first having to rewrite every agent
prompt to emit structured ActionIntent JSON (that prompt-level migration
is tracked separately — see docs/IMPLEMENTATION_PLAN_FROM_GPT_SPEC.md).

Mapping is deterministic and keyword-based; anything unrecognized safely
falls through to the ops.manual_step capability via plan_compiler's
default fallback (never silently dropped, never executed as a guess).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from .models import ActionIntent


# Exact tool_name matches take priority over fuzzy text matching, since
# agents frequently name their tool_name field after the literal
# capability they intend (e.g. "check_table_staleness",
# "cleanup_partial_write") -- this is a far more reliable signal than
# scanning the free-text action_type/reasoning, which can legitimately
# mention multiple related concepts (e.g. a staleness-check step's
# rationale text mentioning "partial writes" as context) without that
# meaning the step's actual TOOL is the other capability.
_EXACT_TOOL_NAME_MAP = {
    "check_table_staleness": "CHECK_TABLE_STALENESS",
    "cleanup_partial_write": "CLEANUP_PARTIAL_WRITE",
    "idempotent_rerun_order_events_job": "RERUN_WRITE_JOB",
    "rerun_ingest_job": "RERUN_INGEST_JOB",
    "verify_row_count_matches_expected": "VERIFY_ROW_COUNT",
}


def _keyword_intent_type(tool_name: str, action_type: str) -> str:
    normalized_tool_name = (tool_name or "").strip().lower()
    if normalized_tool_name in _EXACT_TOOL_NAME_MAP:
        return _EXACT_TOOL_NAME_MAP[normalized_tool_name]

    text = f"{tool_name} {action_type}".lower()
    if "cleanup" in text or "clean up" in text:
        return "CLEANUP_PARTIAL_WRITE"
    if "order_events" in text or ("rerun" in text and "order" in text):
        return "RERUN_WRITE_JOB"
    if "staleness" in text or "stale" in text:
        return "CHECK_TABLE_STALENESS"
    if "verify" in text and "row" in text:
        return "VERIFY_ROW_COUNT"
    if "rerun" in text or "retry" in text or "re-run" in text or "re-trigger" in text or "trigger" in text:
        return "RERUN_INGEST_JOB"
    return "MANUAL"  # deliberately unmapped -> ops.manual_step fallback


def action_step_to_intent(action_step: Dict[str, Any], incident_run_id: str = "", target_resource_id: str = "") -> ActionIntent:
    """
    action_step: a dict with at least action_type, tool_name, parameters_json
    (as already stored in the action_step table).
    """
    tool_name = action_step.get("tool_name", "") or ""
    action_type = action_step.get("action_type", "") or ""
    intent_type = _keyword_intent_type(tool_name, action_type)

    try:
        parameters = json.loads(action_step.get("parameters_json") or "{}")
    except Exception:
        parameters = {}

    # Best-effort default parameters for the run_id-scoped capabilities so
    # that even under-specified legacy steps have SOMETHING to compile
    # against — the precondition_check in each capability will still
    # reject execution if truly required args are missing.
    if intent_type in ("CHECK_TABLE_STALENESS", "CLEANUP_PARTIAL_WRITE", "RERUN_WRITE_JOB", "VERIFY_ROW_COUNT"):
        parameters.setdefault("table_name", "order_events")
        parameters.setdefault("run_id", incident_run_id or parameters.get("run_id", ""))
    if intent_type == "RERUN_INGEST_JOB":
        parameters.setdefault("run_id", incident_run_id or parameters.get("run_id", ""))

    return ActionIntent(
        intent_type=intent_type,
        target_resource_type="POSTGRES_TABLE" if "TABLE" in intent_type or "WRITE" in intent_type else "AWS_LAMBDA_FUNCTION",
        target_resource_id=target_resource_id or parameters.get("table_name") or parameters.get("run_id") or "unknown",
        reason=action_type or tool_name,
        parameters=parameters,
        evidence_ids=[],
        expected_effect=action_type,
    )


def action_steps_to_intents(action_steps: List[Dict[str, Any]], incident_run_id: str = "") -> List[ActionIntent]:
    return [action_step_to_intent(s, incident_run_id=incident_run_id) for s in action_steps]
