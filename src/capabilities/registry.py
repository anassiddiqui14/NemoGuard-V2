"""
The Capability Registry — the "connector catalog" (spec §12.2).

Every capability the platform can execute is registered here exactly once,
with three separate callables:
    precondition_check(args) -> (ok: bool, reason: str)
    execute(args) -> dict            (the real side-effecting call)
    verify(args, execute_result) -> VerificationOutcome

The generic execution engine (execution_engine.py) calls these in a fixed
order for ANY capability — no capability-specific branching exists outside
this file. This directly replaces the two hardcoded if/else branches that
used to live in src/tools/write_tools.py.

Capabilities are intentionally real, small, and match what already exists
in localstack_lab/remediate.py and src/domain/tools/aws_observability_tools.py
— we are wrapping proven working code in a uniform contract, not inventing
new remediation logic.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Tuple

from .models import (
    AutonomyMode,
    CapabilityDefinition,
    CapabilityKind,
    RiskLevel,
    VerificationOutcome,
    VerificationStatus,
)

# capability_id -> (definition, precondition_check, execute, verify)
_REGISTRY: Dict[str, Tuple[CapabilityDefinition, Callable, Callable, Callable]] = {}


def register(
    definition: CapabilityDefinition,
    precondition_check: Callable[[Dict[str, Any]], Tuple[bool, str]],
    execute: Callable[[Dict[str, Any]], Dict[str, Any]],
    verify: Callable[[Dict[str, Any], Dict[str, Any]], VerificationOutcome],
) -> None:
    _REGISTRY[definition.capability_id] = (definition, precondition_check, execute, verify)


def get(capability_id: str):
    """Returns (definition, precondition_check, execute, verify) or raises KeyError."""
    return _REGISTRY[capability_id]


def get_definition(capability_id: str) -> CapabilityDefinition:
    return _REGISTRY[capability_id][0]


def list_capabilities() -> list[CapabilityDefinition]:
    return [d for (d, _, _, _) in _REGISTRY.values()]


def is_registered(capability_id: str) -> bool:
    return capability_id in _REGISTRY


# ---------------------------------------------------------------------------
# Registered capabilities
# ---------------------------------------------------------------------------

def _always_ok(_args: Dict[str, Any]) -> Tuple[bool, str]:
    return True, "no precondition required"


def _no_verify(action_id: str, capability_id: str, status: VerificationStatus = VerificationStatus.SKIPPED) -> VerificationOutcome:
    return VerificationOutcome(
        action_id=action_id,
        capability_id=capability_id,
        status=status,
        checked_at=datetime.now(timezone.utc),
        details={},
        recommended_next_state="",
    )


# --- data.check_table_staleness (READ) --------------------------------------

def _staleness_execute(args: Dict[str, Any]) -> Dict[str, Any]:
    from src.domain.tools.aws_observability_tools import check_table_staleness
    result = json.loads(check_table_staleness(
        args["table_name"], args["run_id"], args.get("expected_row_count")
    ))
    return result


def _staleness_verify(args: Dict[str, Any], execute_result: Dict[str, Any]) -> VerificationOutcome:
    # A read-only diagnostic has no "postcondition" to verify beyond "did it run".
    ok = "error" not in execute_result
    return VerificationOutcome(
        action_id=args.get("_action_id", ""),
        capability_id="data.check_table_staleness",
        status=VerificationStatus.PASSED if ok else VerificationStatus.FAILED,
        checked_at=datetime.now(timezone.utc),
        details=execute_result,
    )


register(
    CapabilityDefinition(
        capability_id="data.check_table_staleness",
        version="1.0.0",
        kind=CapabilityKind.READ,
        description="Compares actual vs expected row count for a run_id to detect a partial write.",
        risk_level=RiskLevel.READ_ONLY,
        autonomy_mode=AutonomyMode.AUTOMATIC,
        supports_dry_run=False,
        required_args=["table_name", "run_id"],
    ),
    _always_ok,
    _staleness_execute,
    _staleness_verify,
)


# --- data.cleanup_partial_write (ACTION, destructive but scoped) ------------

def _cleanup_precondition(args: Dict[str, Any]) -> Tuple[bool, str]:
    from src.domain.tools.aws_observability_tools import check_table_staleness
    staleness = json.loads(check_table_staleness(args["table_name"], args["run_id"]))
    if staleness.get("error"):
        return False, staleness["error"]
    if not staleness.get("is_stale_or_partial"):
        return False, "Table is not currently stale/partial for this run_id; cleanup would be a no-op and is refused."
    return True, "Confirmed partial write present."


def _cleanup_execute(args: Dict[str, Any]) -> Dict[str, Any]:
    from src.domain.tools.aws_observability_tools import cleanup_partial_write
    return json.loads(cleanup_partial_write(
        args["table_name"], args["run_id"], dry_run=args.get("dry_run", True)
    ))


def _cleanup_verify(args: Dict[str, Any], execute_result: Dict[str, Any]) -> VerificationOutcome:
    from src.domain.tools.aws_observability_tools import check_table_staleness
    if execute_result.get("dry_run"):
        # Dry-run cleanup has no real postcondition to check.
        return VerificationOutcome(
            action_id=args.get("_action_id", ""),
            capability_id="data.cleanup_partial_write",
            status=VerificationStatus.SKIPPED,
            checked_at=datetime.now(timezone.utc),
            details=execute_result,
        )
    staleness_after = json.loads(check_table_staleness(args["table_name"], args["run_id"], expected_row_count=0))
    actual = staleness_after.get("actual_row_count")
    ok = actual == 0
    return VerificationOutcome(
        action_id=args.get("_action_id", ""),
        capability_id="data.cleanup_partial_write",
        status=VerificationStatus.PASSED if ok else VerificationStatus.FAILED,
        checked_at=datetime.now(timezone.utc),
        details={"rows_remaining_after_cleanup": actual},
    )


register(
    CapabilityDefinition(
        capability_id="data.cleanup_partial_write",
        version="1.0.0",
        kind=CapabilityKind.ACTION,
        description="Deletes rows for a specific run_id from a table to clean up a genuine partial write, scoped strictly to that run_id.",
        risk_level=RiskLevel.MEDIUM,
        autonomy_mode=AutonomyMode.HUMAN_APPROVAL_REQUIRED,
        supports_dry_run=True,
        required_args=["table_name", "run_id"],
    ),
    _cleanup_precondition,
    _cleanup_execute,
    _cleanup_verify,
)


# --- data.idempotent_rerun_order_events_job (ACTION) ------------------------

def _rerun_order_events_precondition(args: Dict[str, Any]) -> Tuple[bool, str]:
    if not args.get("orders"):
        return False, "orders payload is required to rerun the job"
    return True, "ok"


def _rerun_order_events_execute(args: Dict[str, Any]) -> Dict[str, Any]:
    from localstack_lab.remediate import idempotent_rerun_order_events_job
    return idempotent_rerun_order_events_job(args["run_id"], args["orders"])


def _rerun_order_events_verify(args: Dict[str, Any], execute_result: Dict[str, Any]) -> VerificationOutcome:
    # idempotent_rerun_order_events_job already performs its own final
    # verify_row_count_matches_expected step internally — surface that as
    # the independent verification result rather than trusting "success".
    steps = execute_result.get("steps", [])
    verify_step = next((s for s in steps if s.get("step") == "verify_row_count_matches_expected"), None)
    verified = bool(verify_step and verify_step.get("result", {}).get("verified"))
    return VerificationOutcome(
        action_id=args.get("_action_id", ""),
        capability_id="data.idempotent_rerun_order_events_job",
        status=VerificationStatus.PASSED if verified else VerificationStatus.FAILED,
        checked_at=datetime.now(timezone.utc),
        details=verify_step.get("result", {}) if verify_step else {},
        recommended_next_state="RESOLVED" if verified else "ESCALATED",
    )


register(
    CapabilityDefinition(
        capability_id="data.idempotent_rerun_order_events_job",
        version="1.0.0",
        kind=CapabilityKind.ACTION,
        description="Safe rerun of the order_events write-job: staleness check -> cleanup if needed -> rerun -> verify.",
        risk_level=RiskLevel.MEDIUM,
        autonomy_mode=AutonomyMode.HUMAN_APPROVAL_REQUIRED,
        supports_dry_run=False,
        required_args=["run_id", "orders"],
    ),
    _rerun_order_events_precondition,
    _rerun_order_events_execute,
    _rerun_order_events_verify,
)


# --- compute.rerun_ingest_job (ACTION) ---------------------------------------

def _rerun_ingest_execute(args: Dict[str, Any]) -> Dict[str, Any]:
    from localstack_lab.remediate import rerun_ingest_job
    return rerun_ingest_job(args["run_id"])


def _rerun_ingest_verify(args: Dict[str, Any], execute_result: Dict[str, Any]) -> VerificationOutcome:
    from localstack_lab.remediate import check_job_succeeded, check_alarm_state
    job_check = check_job_succeeded(args["run_id"])
    alarm_check = check_alarm_state()
    resolved = bool(job_check.get("resolved")) and bool(alarm_check.get("resolved"))
    return VerificationOutcome(
        action_id=args.get("_action_id", ""),
        capability_id="compute.rerun_ingest_job",
        status=VerificationStatus.PASSED if resolved else VerificationStatus.FAILED,
        checked_at=datetime.now(timezone.utc),
        details={"job_check": job_check, "alarm_check": alarm_check},
        recommended_next_state="RESOLVED" if resolved else "ESCALATED",
    )


register(
    CapabilityDefinition(
        capability_id="compute.rerun_ingest_job",
        version="1.0.0",
        kind=CapabilityKind.ACTION,
        description="Re-invokes the ingest Lambda with a corrected payload for a run_id (schema-drift style recovery).",
        risk_level=RiskLevel.MEDIUM,
        autonomy_mode=AutonomyMode.HUMAN_APPROVAL_REQUIRED,
        supports_dry_run=False,
        required_args=["run_id"],
    ),
    _always_ok,
    _rerun_ingest_execute,
    _rerun_ingest_verify,
)


# --- ops.verify_row_count_matches_expected (READ) ---------------------------

def _verify_row_count_execute(args: Dict[str, Any]) -> Dict[str, Any]:
    from src.domain.tools.aws_observability_tools import verify_row_count_matches_expected
    return json.loads(verify_row_count_matches_expected(
        args["table_name"], args["run_id"], args["expected_row_count"]
    ))


def _verify_row_count_verify(args: Dict[str, Any], execute_result: Dict[str, Any]) -> VerificationOutcome:
    verified = bool(execute_result.get("verified"))
    return VerificationOutcome(
        action_id=args.get("_action_id", ""),
        capability_id="ops.verify_row_count_matches_expected",
        status=VerificationStatus.PASSED if verified else VerificationStatus.FAILED,
        checked_at=datetime.now(timezone.utc),
        details=execute_result,
    )


register(
    CapabilityDefinition(
        capability_id="ops.verify_row_count_matches_expected",
        version="1.0.0",
        kind=CapabilityKind.READ,
        description="Confirms a table has exactly the expected row count for a run_id after remediation.",
        risk_level=RiskLevel.READ_ONLY,
        autonomy_mode=AutonomyMode.AUTOMATIC,
        supports_dry_run=False,
        required_args=["table_name", "run_id", "expected_row_count"],
    ),
    _always_ok,
    _verify_row_count_execute,
    _verify_row_count_verify,
)


# --- ops.manual_step (ACTION, fallback for non-automatable steps) -----------
# Whenever a plan step cannot be mapped to a real registered capability
# (e.g. "escalate to on-call engineer for manual review"), it is compiled to
# this capability rather than silently dropped or executed as a no-op. Its
# "execution" is simply recording that a human must act, and its
# "verification" always requires human sign-off (INCONCLUSIVE, never
# auto-PASSED) — this directly satisfies the spec's "no self-verification"
# principle (§37.7) for steps we cannot mechanically verify.

def _manual_step_execute(args: Dict[str, Any]) -> Dict[str, Any]:
    return {"note": "Manual step recorded. Requires human action and human-confirmed resolution.", "instructions": args.get("instructions", "")}


def _manual_step_verify(args: Dict[str, Any], execute_result: Dict[str, Any]) -> VerificationOutcome:
    return VerificationOutcome(
        action_id=args.get("_action_id", ""),
        capability_id="ops.manual_step",
        status=VerificationStatus.INCONCLUSIVE,
        checked_at=datetime.now(timezone.utc),
        details=execute_result,
        recommended_next_state="ESCALATED",
    )


register(
    CapabilityDefinition(
        capability_id="ops.manual_step",
        version="1.0.0",
        kind=CapabilityKind.ACTION,
        description="Fallback for any recovery step that cannot be mapped to a real automatable capability; always requires human verification.",
        risk_level=RiskLevel.LOW,
        autonomy_mode=AutonomyMode.HUMAN_APPROVAL_REQUIRED,
        supports_dry_run=False,
        required_args=[],
    ),
    _always_ok,
    _manual_step_execute,
    _manual_step_verify,
)
