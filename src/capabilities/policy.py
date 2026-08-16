"""
Deterministic policy decisions (spec §13.1) — risk classification and
approval requirements are computed HERE, in code, never inferred from an
LLM prompt. This is the structural enforcement layer that the spec
emphasizes repeatedly: "models propose; policy decides; deterministic code
executes."

Admin-configurable overrides: config/capability_policy.yaml (spec §3.2 /
§17.4, scoped down per docs/IMPLEMENTATION_PLAN_FROM_GPT_SPEC.md Part
2.2) can override a capability's risk_level/autonomy_mode without a code
change. Precedence: YAML override > Python-defined registry default.
Unknown capability_ids in the YAML are ignored (fail-safe: a config typo
never silently grants MORE access than the code default).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
from pydantic import BaseModel

from .models import AutonomyMode, CompiledAction, RiskLevel

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "capability_policy.yaml"
_CONFIG_PATH = Path(os.environ.get("NEMOGUARD_CAPABILITY_POLICY_PATH", str(_DEFAULT_CONFIG_PATH)))

_overrides_cache: Optional[Dict[str, Dict[str, str]]] = None


def _load_overrides() -> Dict[str, Dict[str, str]]:
    """Loads config/capability_policy.yaml into a
    {capability_id: {"risk_level": ..., "autonomy_mode": ...}} map.
    Missing file or parse error -> empty overrides (fail-safe: falls back
    to Python defaults, never crashes policy evaluation)."""
    global _overrides_cache
    if _overrides_cache is not None:
        return _overrides_cache
    try:
        with open(_CONFIG_PATH, "r") as f:
            raw = yaml.safe_load(f) or {}
        _overrides_cache = raw.get("capabilities", {}) or {}
    except Exception:
        _overrides_cache = {}
    return _overrides_cache


def reload_policy_config() -> None:
    """Forces the next policy evaluation to re-read capability_policy.yaml
    from disk. Exposed so an admin API endpoint can trigger a live reload
    without restarting the process."""
    global _overrides_cache
    _overrides_cache = None


def _effective_risk_and_autonomy(action: CompiledAction) -> Tuple[RiskLevel, AutonomyMode]:
    overrides = _load_overrides().get(action.capability_id)
    if not overrides:
        return action.risk_level, action.autonomy_mode
    try:
        risk = RiskLevel(overrides.get("risk_level", action.risk_level.value))
    except ValueError:
        risk = action.risk_level
    try:
        autonomy = AutonomyMode(overrides.get("autonomy_mode", action.autonomy_mode.value))
    except ValueError:
        autonomy = action.autonomy_mode
    return risk, autonomy


class PolicyDecision(BaseModel):
    action_id: str
    decision: str  # "AUTO_ALLOWED" | "REQUIRE_APPROVAL" | "DENIED"
    reasons: List[str]


def evaluate_action(action: CompiledAction) -> PolicyDecision:
    risk_level, autonomy_mode = _effective_risk_and_autonomy(action)

    if risk_level == RiskLevel.PROHIBITED or autonomy_mode == AutonomyMode.PROHIBITED:
        return PolicyDecision(
            action_id=action.action_id,
            decision="DENIED",
            reasons=[f"Capability {action.capability_id} is prohibited by policy."],
        )

    if autonomy_mode == AutonomyMode.AUTOMATIC and risk_level == RiskLevel.READ_ONLY:
        return PolicyDecision(
            action_id=action.action_id,
            decision="AUTO_ALLOWED",
            reasons=["Read-only diagnostic capability; automatically allowed."],
        )

    return PolicyDecision(
        action_id=action.action_id,
        decision="REQUIRE_APPROVAL",
        reasons=[
            f"Capability {action.capability_id} has risk_level={risk_level.value} "
            f"and autonomy_mode={autonomy_mode.value}; human approval required."
        ],
    )


def evaluate_plan(actions: List[CompiledAction]) -> List[PolicyDecision]:
    return [evaluate_action(a) for a in actions]


def plan_requires_approval(actions: List[CompiledAction]) -> bool:
    return any(d.decision == "REQUIRE_APPROVAL" for d in evaluate_plan(actions))


def plan_has_denied_action(actions: List[CompiledAction]) -> bool:
    return any(d.decision == "DENIED" for d in evaluate_plan(actions))
