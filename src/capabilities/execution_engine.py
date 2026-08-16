"""
The generic execution engine (spec §12.6) — the single code path that
executes ANY compiled action against ANY registered capability.

Sequence per action, exactly as the spec requires:
    1. re-check preconditions (state may have changed since compile time)
    2. dry-run if supported (record result, but do not treat as final)
    3. execute for real
    4. persist exact request/response
    5. run independent verification (never trust the execute() return value)
    6. return a structured ActionExecutionRecord the caller can persist/audit

This directly replaces the hardcoded "PASSED" verification_result rows
that orchestrator.execute_plan used to insert unconditionally, and the two
if/else branches that used to live in write_tools.execute_simulated_action.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from pydantic import BaseModel

from . import policy, registry
from .models import (
    ActionResult,
    ActionResultStatus,
    CompiledAction,
    VerificationOutcome,
    VerificationStatus,
)


class ActionExecutionRecord(BaseModel):
    """Full record of one action's execution + verification, ready to persist."""
    action_id: str
    capability_id: str
    precondition_ok: bool
    precondition_reason: str
    result: ActionResult
    verification: VerificationOutcome


def execute_compiled_action(action: CompiledAction, dry_run_first: bool = True) -> ActionExecutionRecord:
    """
    Executes a single compiled action through its registered capability's
    precondition_check -> execute -> verify triplet. This function has NO
    capability-specific branching — it works identically for every
    capability_id in the registry.
    """
    if not registry.is_registered(action.capability_id):
        now = datetime.now(timezone.utc)
        result = ActionResult(
            action_id=action.action_id,
            capability_id=action.capability_id,
            status=ActionResultStatus.FAILED,
            started_at=now,
            completed_at=now,
            error_message=f"Capability {action.capability_id} is not registered.",
        )
        verification = VerificationOutcome(
            action_id=action.action_id,
            capability_id=action.capability_id,
            status=VerificationStatus.FAILED,
            checked_at=now,
            details={"reason": "unregistered_capability"},
            recommended_next_state="ESCALATED",
        )
        return ActionExecutionRecord(
            action_id=action.action_id,
            capability_id=action.capability_id,
            precondition_ok=False,
            precondition_reason="Capability not registered.",
            result=result,
            verification=verification,
        )

    # Step 0: re-check policy NOW, at execution time -- not just at
    # compile/approval time. If an admin has since marked this capability
    # DENIED via config/capability_policy.yaml (or a capability was always
    # PROHIBITED in code), refuse to execute regardless of what was
    # approved earlier. This closes the gap where policy could otherwise
    # be checked once at approval time and then silently bypassed by a
    # direct call to execute_compiled_action.
    decision = policy.evaluate_action(action)
    if decision.decision == "DENIED":
        now = datetime.now(timezone.utc)
        result = ActionResult(
            action_id=action.action_id,
            capability_id=action.capability_id,
            status=ActionResultStatus.FAILED,
            started_at=now,
            completed_at=now,
            error_message=f"Policy denied execution: {'; '.join(decision.reasons)}",
        )
        verification = VerificationOutcome(
            action_id=action.action_id,
            capability_id=action.capability_id,
            status=VerificationStatus.SKIPPED,
            checked_at=now,
            details={"reason": "policy_denied", "policy_reasons": decision.reasons},
            recommended_next_state="ESCALATED",
        )
        return ActionExecutionRecord(
            action_id=action.action_id,
            capability_id=action.capability_id,
            precondition_ok=False,
            precondition_reason="Policy denied.",
            result=result,
            verification=verification,
        )

    _definition, precondition_check, execute, verify = registry.get(action.capability_id)

    args: Dict[str, Any] = dict(action.arguments)
    args["_action_id"] = action.action_id

    # Step 1: re-check preconditions NOW (not at compile/approval time).
    try:
        precondition_ok, precondition_reason = precondition_check(args)
    except Exception as e:
        precondition_ok, precondition_reason = False, f"Precondition check raised: {e}"

    started_at = datetime.now(timezone.utc)

    if not precondition_ok:
        result = ActionResult(
            action_id=action.action_id,
            capability_id=action.capability_id,
            status=ActionResultStatus.PRECONDITION_FAILED,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            error_message=precondition_reason,
        )
        verification = VerificationOutcome(
            action_id=action.action_id,
            capability_id=action.capability_id,
            status=VerificationStatus.SKIPPED,
            checked_at=datetime.now(timezone.utc),
            details={"reason": "precondition_failed"},
            recommended_next_state="ESCALATED",
        )
        return ActionExecutionRecord(
            action_id=action.action_id,
            capability_id=action.capability_id,
            precondition_ok=False,
            precondition_reason=precondition_reason,
            result=result,
            verification=verification,
        )

    # Step 2 (optional dry run) is handled by the capability itself via a
    # `dry_run` argument (e.g. data.cleanup_partial_write) — the engine
    # doesn't need special-case logic for this, it just passes through
    # whatever arguments the compiled action carries.

    # Step 3: real execution.
    try:
        raw_result = execute(args)
        error_in_result = isinstance(raw_result, dict) and raw_result.get("error")
        status = ActionResultStatus.FAILED if error_in_result else ActionResultStatus.SUCCESS
        if isinstance(raw_result, dict) and raw_result.get("dry_run") is True and dry_run_first:
            status = ActionResultStatus.DRY_RUN_ONLY
        error_message = raw_result.get("error") if isinstance(raw_result, dict) else None
    except Exception as e:
        raw_result = {"error": str(e)}
        status = ActionResultStatus.FAILED
        error_message = str(e)

    completed_at = datetime.now(timezone.utc)
    result = ActionResult(
        action_id=action.action_id,
        capability_id=action.capability_id,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        raw_result=raw_result if isinstance(raw_result, dict) else {"value": raw_result},
        error_message=error_message,
    )

    # Step 4: independent verification — NEVER trust `status == SUCCESS`
    # alone. The capability's own verify() re-checks real state.
    if status == ActionResultStatus.FAILED:
        verification = VerificationOutcome(
            action_id=action.action_id,
            capability_id=action.capability_id,
            status=VerificationStatus.SKIPPED,
            checked_at=datetime.now(timezone.utc),
            details={"reason": "execution_failed_before_verification"},
            recommended_next_state="ESCALATED",
        )
    else:
        try:
            verification = verify(args, result.raw_result)
        except Exception as e:
            verification = VerificationOutcome(
                action_id=action.action_id,
                capability_id=action.capability_id,
                status=VerificationStatus.INCONCLUSIVE,
                checked_at=datetime.now(timezone.utc),
                details={"error": f"Verification raised: {e}"},
                recommended_next_state="ESCALATED",
            )

    return ActionExecutionRecord(
        action_id=action.action_id,
        capability_id=action.capability_id,
        precondition_ok=True,
        precondition_reason=precondition_reason,
        result=result,
        verification=verification,
    )
