from .enums import IncidentState

class InvalidTransitionError(Exception):
    pass

class StateMachine:
    """
    Enforces valid state transitions for the Incident lifecycle.
    
    Valid Transitions:
    DETECTED -> CORRELATING
    CORRELATING -> TRIAGING | FAILED
    TRIAGING -> INVESTIGATING | FAILED
    INVESTIGATING -> PLAN_READY | FAILED
    PLAN_READY -> AWAITING_APPROVAL | INVESTIGATING
    AWAITING_APPROVAL -> EXECUTING | INVESTIGATING | CANCELLED
    EXECUTING -> VERIFYING | ROLLED_BACK | FAILED
    VERIFYING -> RESOLVED | ROLLED_BACK | FAILED
    ROLLED_BACK -> INVESTIGATING | FAILED
    """
    
    TRANSITIONS = {
        IncidentState.DETECTED: {IncidentState.CORRELATING},
        IncidentState.CORRELATING: {IncidentState.TRIAGING, IncidentState.FAILED},
        IncidentState.TRIAGING: {IncidentState.INVESTIGATING, IncidentState.FAILED},
        IncidentState.INVESTIGATING: {IncidentState.PLAN_READY, IncidentState.FAILED},
        IncidentState.PLAN_READY: {IncidentState.AWAITING_APPROVAL, IncidentState.INVESTIGATING},
        IncidentState.AWAITING_APPROVAL: {IncidentState.EXECUTING, IncidentState.INVESTIGATING, IncidentState.CANCELLED},
        IncidentState.EXECUTING: {IncidentState.VERIFYING, IncidentState.ROLLED_BACK, IncidentState.FAILED},
        IncidentState.VERIFYING: {IncidentState.RESOLVED, IncidentState.ROLLED_BACK, IncidentState.FAILED},
        IncidentState.ROLLED_BACK: {IncidentState.INVESTIGATING, IncidentState.FAILED},
        IncidentState.RESOLVED: set(),
        IncidentState.FAILED: set(),
        IncidentState.CANCELLED: set(),
    }

    @classmethod
    def validate_transition(cls, current_state: str, new_state: str) -> None:
        try:
            current = IncidentState(current_state)
            new = IncidentState(new_state)
        except ValueError:
            raise InvalidTransitionError(f"Invalid state enum provided: {current_state} -> {new_state}")
            
        allowed = cls.TRANSITIONS.get(current, set())
        if new not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition from {current.value} to {new.value}. "
                f"Allowed transitions: {[s.value for s in allowed]}"
            )
