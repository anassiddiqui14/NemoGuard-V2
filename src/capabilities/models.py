"""
Typed contracts for the Governed Capability Gateway.

These replace free-text action_step.tool_name/action_type strings with a
structured pipeline:

    ActionIntent (what an agent/human wants to happen, abstractly)
        -> compile_plan()
    CompiledAction (resolved to a real registered capability + exact args)
        -> plan hash -> approval
    ActionResult (what actually happened when it executed)
    VerificationOutcome (independent proof it worked, or didn't)

See docs/nemoguard_real_world_support_engineer_build_spec.md §12.4-§12.6 and
docs/IMPLEMENTATION_PLAN_FROM_GPT_SPEC.md Part 1.1-1.3.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    READ_ONLY = "READ_ONLY"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    PROHIBITED = "PROHIBITED"


class AutonomyMode(str, Enum):
    AUTOMATIC = "AUTOMATIC"                       # no approval needed at all
    HUMAN_APPROVAL_REQUIRED = "HUMAN_APPROVAL_REQUIRED"
    DUAL_APPROVAL_REQUIRED = "DUAL_APPROVAL_REQUIRED"
    PROHIBITED = "PROHIBITED"                      # never allowed to execute


class ActionIntent(BaseModel):
    """
    What an agent (or a human, via the API) wants to happen — abstract,
    NOT a function name. The Plan Compiler resolves this to a real
    capability. This is the only shape an LLM is allowed to emit for a
    write/action step; it can never emit a raw tool_name or code.
    """
    intent_type: str = Field(..., description="Abstract action type, e.g. RERUN_WRITE_JOB, CLEANUP_PARTIAL_WRITE")
    target_resource_type: str = Field(..., description="e.g. 'POSTGRES_TABLE', 'AWS_LAMBDA_FUNCTION'")
    target_resource_id: str = Field(..., description="Canonical identifier for the target, e.g. table name or ARN")
    reason: str = Field(..., description="Why this action is being proposed, human-readable")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    evidence_ids: List[str] = Field(default_factory=list)
    expected_effect: str = ""


class CompiledAction(BaseModel):
    """
    The deterministic, code-produced resolution of an ActionIntent to a
    real registered capability with exact arguments. This is what gets
    hashed and bound to an approval — never the free-text intent.
    """
    action_id: str
    sequence: int
    capability_id: str
    capability_version: str
    intent_type: str
    target_resource_type: str
    target_resource_id: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel
    autonomy_mode: AutonomyMode
    supports_dry_run: bool = False
    idempotency_key: str
    evidence_ids: List[str] = Field(default_factory=list)
    expected_effect: str = ""


class CompiledPlan(BaseModel):
    """A full compiled, hashable recovery plan — the output of the Plan Compiler."""
    plan_id: str
    incident_id: str
    plan_version: int
    actions: List[CompiledAction]
    plan_hash: str
    compiled_at: datetime


class ActionResultStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"
    DRY_RUN_ONLY = "DRY_RUN_ONLY"
    SKIPPED = "SKIPPED"


class ActionResult(BaseModel):
    action_id: str
    capability_id: str
    status: ActionResultStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    raw_result: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None


class VerificationStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"
    SKIPPED = "SKIPPED"


class VerificationOutcome(BaseModel):
    """
    Independent proof that an action actually achieved its intended effect.
    An action's own "SUCCESS" result is NEVER sufficient on its own — see
    spec §14.1. This is produced by a capability's own `verify` callable,
    which re-checks real state (not the action's return value).
    """
    action_id: str
    capability_id: str
    status: VerificationStatus
    checked_at: datetime
    details: Dict[str, Any] = Field(default_factory=dict)
    recommended_next_state: str = ""  # e.g. "RESOLVED", "ROLLED_BACK", "ESCALATED"


class CapabilityKind(str, Enum):
    READ = "READ"
    ACTION = "ACTION"


class CapabilityDefinition(BaseModel):
    """
    A single entry in the capability registry — the "connector catalog"
    (spec §12.2). Each capability declares its own precondition check,
    executor, and verifier as separate callables so the generic execution
    engine never needs capability-specific branching.
    """
    capability_id: str
    version: str
    kind: CapabilityKind
    description: str
    risk_level: RiskLevel
    autonomy_mode: AutonomyMode
    supports_dry_run: bool = False
    required_args: List[str] = Field(default_factory=list)
    owner: str = "platform"

    class Config:
        arbitrary_types_allowed = True
