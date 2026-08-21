"""
Unit tests for src/domain/state_machine.py -- the authoritative validator
for IncidentState lifecycle transitions.

Per docs/NemoGuard_Enterprise_Hardening_and_Productization_Build_Plan.md
WP-001 ("add state machine unit tests"). No external dependencies (DB,
network) required -- pure logic tests against StateMachine.TRANSITIONS.
"""

import pytest

from src.domain.enums import IncidentState
from src.domain.state_machine import StateMachine, InvalidTransitionError


class TestValidTransitions:
    """Every edge explicitly present in StateMachine.TRANSITIONS must validate without raising."""

    @pytest.mark.parametrize(
        "current,new",
        [
            (IncidentState.DETECTED, IncidentState.CORRELATING),
            (IncidentState.DETECTED, IncidentState.RESOLVED),
            (IncidentState.CORRELATING, IncidentState.TRIAGING),
            (IncidentState.CORRELATING, IncidentState.FAILED),
            (IncidentState.CORRELATING, IncidentState.RESOLVED),
            (IncidentState.TRIAGING, IncidentState.INVESTIGATING),
            (IncidentState.TRIAGING, IncidentState.FAILED),
            (IncidentState.TRIAGING, IncidentState.RESOLVED),
            (IncidentState.INVESTIGATING, IncidentState.PLAN_READY),
            (IncidentState.INVESTIGATING, IncidentState.FAILED),
            (IncidentState.INVESTIGATING, IncidentState.RESOLVED),
            (IncidentState.PLAN_READY, IncidentState.AWAITING_APPROVAL),
            (IncidentState.PLAN_READY, IncidentState.INVESTIGATING),
            (IncidentState.PLAN_READY, IncidentState.RESOLVED),
            (IncidentState.AWAITING_APPROVAL, IncidentState.EXECUTING),
            (IncidentState.AWAITING_APPROVAL, IncidentState.INVESTIGATING),
            (IncidentState.AWAITING_APPROVAL, IncidentState.CANCELLED),
            (IncidentState.AWAITING_APPROVAL, IncidentState.RESOLVED),
            (IncidentState.EXECUTING, IncidentState.VERIFYING),
            (IncidentState.EXECUTING, IncidentState.ROLLED_BACK),
            (IncidentState.EXECUTING, IncidentState.FAILED),
            (IncidentState.VERIFYING, IncidentState.RESOLVED),
            (IncidentState.VERIFYING, IncidentState.ROLLED_BACK),
            (IncidentState.VERIFYING, IncidentState.FAILED),
            (IncidentState.ROLLED_BACK, IncidentState.INVESTIGATING),
            (IncidentState.ROLLED_BACK, IncidentState.FAILED),
        ],
    )
    def test_allowed_transition_does_not_raise(self, current, new):
        # Should not raise.
        StateMachine.validate_transition(current.value, new.value)


class TestInvalidTransitions:
    """Transitions that must be rejected."""

    @pytest.mark.parametrize(
        "current,new",
        [
            (IncidentState.DETECTED, IncidentState.EXECUTING),
            (IncidentState.DETECTED, IncidentState.PLAN_READY),
            (IncidentState.RESOLVED, IncidentState.INVESTIGATING),
            (IncidentState.RESOLVED, IncidentState.EXECUTING),
            (IncidentState.FAILED, IncidentState.RESOLVED),
            (IncidentState.FAILED, IncidentState.INVESTIGATING),
            (IncidentState.CANCELLED, IncidentState.INVESTIGATING),
            (IncidentState.EXECUTING, IncidentState.PLAN_READY),
            (IncidentState.VERIFYING, IncidentState.EXECUTING),
            (IncidentState.PLAN_READY, IncidentState.EXECUTING),  # must go through AWAITING_APPROVAL
            (IncidentState.CORRELATING, IncidentState.EXECUTING),
        ],
    )
    def test_disallowed_transition_raises(self, current, new):
        with pytest.raises(InvalidTransitionError):
            StateMachine.validate_transition(current.value, new.value)

    def test_self_transition_raises(self):
        # No state is its own allowed transition target (no-op self-loops disallowed).
        for state in IncidentState:
            with pytest.raises(InvalidTransitionError):
                StateMachine.validate_transition(state.value, state.value)

    def test_terminal_states_have_no_outgoing_transitions(self):
        for terminal in (IncidentState.RESOLVED, IncidentState.FAILED, IncidentState.CANCELLED):
            assert StateMachine.TRANSITIONS[terminal] == set()

    def test_invalid_enum_value_raises(self):
        with pytest.raises(InvalidTransitionError):
            StateMachine.validate_transition("NOT_A_REAL_STATE", IncidentState.RESOLVED.value)
        with pytest.raises(InvalidTransitionError):
            StateMachine.validate_transition(IncidentState.DETECTED.value, "NOT_A_REAL_STATE")


class TestTransitionsTableIntegrity:
    """Structural sanity checks on the transition table itself."""

    def test_every_state_has_an_entry(self):
        for state in IncidentState:
            assert state in StateMachine.TRANSITIONS, f"{state} missing from TRANSITIONS table"

    def test_no_state_transitions_to_itself(self):
        for state, targets in StateMachine.TRANSITIONS.items():
            assert state not in targets, f"{state} must not list itself as an allowed target"
