"""
The deterministic Plan Compiler (spec §12.5).

Converts a list of abstract ActionIntent objects (produced by an LLM agent)
into a CompiledPlan of CompiledAction objects bound to real, registered
capabilities, with a stable content hash for approval-integrity binding.

No LLM output is trusted to name a capability directly — the compiler is
the only place that resolves an intent_type string to a capability_id, via
the explicit INTENT_TO_CAPABILITY map below. Unknown/unmappable intents are
rejected before execution: a human must perform or translate the action into
a registered governed capability.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from . import registry
from .models import ActionIntent, CompiledAction, CompiledPlan


class UnsupportedCapabilityError(ValueError):
    """Raised when a plan contains an intent with no registered capability."""

    code = "MANUAL_ACTION_REQUIRED"

    def __init__(self, intent: ActionIntent):
        self.intent = intent
        super().__init__(
            f"{self.code}: intent_type={intent.intent_type!r} has no registered "
            f"governed capability (reason: {intent.reason!r})"
        )


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
    capability_id = INTENT_TO_CAPABILITY.get(intent.intent_type)
    if not capability_id:
        raise UnsupportedCapabilityError(intent)
    if not registry.is_registered(capability_id):
        raise RuntimeError(
            f"Capability mapping for intent_type={intent.intent_type!r} points to "
            f"unregistered capability {capability_id!r}"
        )
    return capability_id


def _compute_idempotency_key(
    incident_id: str,
    plan_version: int,
    sequence: int,
    capability_id: str,
    arguments: Dict[str, Any],
) -> str:
    payload = json.dumps(
        {
            "incident_id": incident_id,
            "plan_version": plan_version,
            "sequence": sequence,
            "capability_id": capability_id,
            "arguments": arguments,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def compile_action(
    intent: ActionIntent, incident_id: str, plan_version: int, sequence: int
) -> CompiledAction:
    capability_id = _resolve_capability_id(intent)
    definition = registry.get_definition(capability_id)
    arguments = dict(intent.parameters)

    action_id = f"ACT-{uuid.uuid4().hex[:10].upper()}"
    idempotency_key = _compute_idempotency_key(
        incident_id, plan_version, sequence, capability_id, arguments
    )

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


def _hash_compiled_plan(
    incident_id: str, plan_version: int, actions: List[CompiledAction]
) -> str:
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


def compile_plan(
    incident_id: str, plan_id: str, plan_version: int, intents: List[ActionIntent]
) -> CompiledPlan:
    """
    The single entry point for turning a list of agent-proposed ActionIntents
    into a hashable, executable CompiledPlan. Deterministic: same intents in,
    same compiled plan + hash out.

    Raises:
        UnsupportedCapabilityError: an intent is not mapped to a registered,
            governed capability. Callers must require manual action rather
            than route it through a generic execution fallback.
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
