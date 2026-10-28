"""Regression tests for execution-result aggregation safety invariants."""

from datetime import datetime, timezone

import pytest

from src.capabilities.execution_engine import ActionExecutionRecord, is_resolution_verified
from src.capabilities.models import (
    ActionResult,
    ActionResultStatus,
    VerificationOutcome,
    VerificationStatus,
)


def make_record(
    result_status: ActionResultStatus,
    verification_status: VerificationStatus,
) -> ActionExecutionRecord:
    now = datetime.now(timezone.utc)
    return ActionExecutionRecord(
        action_id="ACT-1",
        capability_id="test.capability",
        precondition_ok=result_status == ActionResultStatus.SUCCESS,
        precondition_reason="test",
        result=ActionResult(
            action_id="ACT-1",
            capability_id="test.capability",
            status=result_status,
            started_at=now,
            completed_at=now,
        ),
        verification=VerificationOutcome(
            action_id="ACT-1",
            capability_id="test.capability",
            status=verification_status,
            checked_at=now,
        ),
    )


def test_successful_execution_with_passed_verification_qualifies_for_resolution():
    assert is_resolution_verified(
        make_record(ActionResultStatus.SUCCESS, VerificationStatus.PASSED)
    )


@pytest.mark.parametrize("result_status", list(ActionResultStatus))
def test_only_successful_execution_can_qualify_for_resolution(result_status):
    record = make_record(result_status, VerificationStatus.PASSED)

    assert is_resolution_verified(record) is (result_status == ActionResultStatus.SUCCESS)


@pytest.mark.parametrize("verification_status", list(VerificationStatus))
def test_only_passed_independent_verification_can_qualify_for_resolution(verification_status):
    record = make_record(ActionResultStatus.SUCCESS, verification_status)

    assert is_resolution_verified(record) is (
        verification_status == VerificationStatus.PASSED
    )
