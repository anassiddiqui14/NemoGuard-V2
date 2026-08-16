"""
The deterministic Plan Compiler (spec §12.5).

Converts a list of abstract ActionIntent objects (produced by an LLM agent)
into a CompiledPlan of CompiledAction objects bound to real, registered
capabilities, with a stable content hash for approval-integrity binding.

No LLM output is trusted to name a capability directly — the compiler is
the only place that resolves an intent_type string to a capability_id, via
the explicit INTENT_TO_CAPABILITY map below. Unknown/unmappable intents are
compiled to the safe `ops.manual_step` fallback rather than dropped.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from . import registry
from .models import ActionIntent, CompiledAction, CompiledPlan


# Deterministic, explicit mapping from abstract intent types (used by
# agents/prompts) to concrete registered capability IDs. This is the ONLY
# place this mapping exists — extend it when a new capability is registered.
INTENT_TO_CAPABILITY: Dict[str, str] = {
    "CHECK_TABLE_STALENESS": "data.check_table_staleness",
    "CLEANUP_PARTIAL_WRITE": "data.cleanup_partial_write",
    "RERUN_WRITE_JOB": "data.idempotent_rerun_order_events_job",
    "RERUN_INGEST_JOB": "compute.rerun_ingest_job",
    "VERIFY_ROW_COUNT": "ops.verify_row_count_matches_expected",
}


def _resolve_capability_id(intent: ActionIntent) -> str:
    return INTENT_TO_CAPABILITY.get(intent.intent_type, "ops.manual_step")


def _compute_idempotency_key(incident_id: str, plan_version: int, sequence: int, capability_id: str, arguments: Dict[str, Any]) -> str:
    payload = json.dumps({"incident_id": incident_id, "plan_version": plan_version, "sequence": sequence, "capability_id": capability_id, "arguments": arguments}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def compile_action(intent: ActionIntent, incident_id: str, plan_version: int, sequence: int) -> CompiledAction:
    capability_id = _resolve_capability_id(intent)

    if registry.is_registered(capability_id):
        definition = registry.get_definition(capability_id)
    else:
        # Should never happen given the fallback above, but fail safe.
        capability_id = "ops.manual_step"
        definition = registry.get_definition(capability_id)

    arguments = dict(intent.parameters)
    # For the manual-step fallback, always carry the original intent's
    # reason/expected_effect so a human has full context.
    if capability_id == "ops.manual_step":
        arguments.setdefault("instructions", f"{intent.intent_type}: {intent.reason} (target: {intent.target_resource_type}/{intent.target_resource_id})")

    action_id = f"ACT-{uuid.uuid4().hex[:10].upper()}"
    idempotency_key = _compute_idempotency_key(incident_id, plan_version, sequence, capability_id, arguments)

    return CompiledAction(
        action_id=action_id,
        sequence=sequence,
        capability_id=capability_id,
        capability_version=definition.version,
        intent_type=intent.intent_type,
        target_resource_type=intent.target_resource_type,
        target_resource_id=intent.target_resource_id,
        arguments=arguments,
        risk_level=definition.risk_level,
        autonomy_mode=definition.autonomy_mode,
        supports_dry_run=definition.supports_dry_run,
        idempotency_key=idempotency_key,
        evidence_ids=intent.evidence_ids,
        expected_effect=intent.expected_effect,
    )


def _hash_compiled_plan(incident_id: str, plan_version: int, actions: List[CompiledAction]) -> str:
    payload = {
        "incident_id": incident_id,
        "plan_version": plan_version,
        "actions": [
            {
                "sequence": a.sequence,
                "capability_id": a.capability_id,
                "capability_version": a.capability_version,
                "target_resource_type": a.target_resource_type,
                "target_resource_id": a.target_resource_id,
                "arguments": a.arguments,
                "risk_level": a.risk_level.value,
            }
            for a in sorted(actions, key=lambda a: a.sequence)
        ],
    }
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compile_plan(incident_id: str, plan_id: str, plan_version: int, intents: List[ActionIntent]) -> CompiledPlan:
    """
    The single entry point for turning a list of agent-proposed ActionIntents
    into a hashable, executable CompiledPlan. Deterministic: same intents in,
    same compiled plan + hash out.
    """
    actions = [
        compile_action(intent, incident_id, plan_version, sequence=i + 1)
        for i, intent in enumerate(intents)
    ]
    plan_hash = _hash_compiled_plan(incident_id, plan_version, actions)
    return CompiledPlan(
        plan_id=plan_id,
        incident_id=incident_id,
        plan_version=plan_version,
        actions=actions,
        plan_hash=plan_hash,
        compiled_at=datetime.now(timezone.utc),
    )
