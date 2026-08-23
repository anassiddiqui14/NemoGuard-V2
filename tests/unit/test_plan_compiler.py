import pytest

from src.capabilities.models import ActionIntent
from src.capabilities.plan_compiler import (
    UnsupportedCapabilityError,
    compile_plan,
)


def _intent(intent_type: str) -> ActionIntent:
    return ActionIntent(
        intent_type=intent_type,
        target_resource_type="POSTGRES_TABLE",
        target_resource_id="order_events",
        reason="Controlled recovery action",
        parameters={"run_id": "run-123"},
    )


def test_compile_plan_resolves_known_intent_to_registered_governed_capability():
    compiled = compile_plan(
        incident_id="INC-001",
        plan_id="PLN-001",
        plan_version=1,
        intents=[_intent("RERUN_WRITE_JOB")],
    )

    assert len(compiled.actions) == 1
    assert compiled.actions[0].capability_id == "data.idempotent_rerun_order_events_job"
    assert compiled.actions[0].capability_id != "ops.manual_step"
    assert compiled.plan_hash


def test_compile_plan_rejects_unmapped_intent_before_any_execution_path():
    with pytest.raises(UnsupportedCapabilityError) as exc_info:
        compile_plan(
            incident_id="INC-001",
            plan_id="PLN-001",
            plan_version=1,
            intents=[_intent("RUN_ARBITRARY_SHELL_COMMAND")],
        )

    assert exc_info.value.code == "MANUAL_ACTION_REQUIRED"
    assert exc_info.value.intent.intent_type == "RUN_ARBITRARY_SHELL_COMMAND"
    assert "ops.manual_step" not in str(exc_info.value)


def test_compile_plan_rejects_legacy_manual_intent():
    with pytest.raises(UnsupportedCapabilityError) as exc_info:
        compile_plan(
            incident_id="INC-001",
            plan_id="PLN-001",
            plan_version=1,
            intents=[_intent("MANUAL")],
        )

    assert exc_info.value.code == "MANUAL_ACTION_REQUIRED"
