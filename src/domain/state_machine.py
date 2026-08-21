from .enums import IncidentState

class InvalidTransitionError(Exception):
    pass

class StateMachine:
    """
    Enforces valid state transitions for the Incident lifecycle.
    
    Valid Transitions:
    DETECTED -> CORRELATING | RESOLVED
    CORRELATING -> TRIAGING | FAILED | RESOLVED
    TRIAGING -> INVESTIGATING | FAILED | RESOLVED
    INVESTIGATING -> PLAN_READY | FAILED | RESOLVED
    PLAN_READY -> AWAITING_APPROVAL | INVESTIGATING | RESOLVED
    AWAITING_APPROVAL -> EXECUTING | INVESTIGATING | CANCELLED | RESOLVED
    EXECUTING -> VERIFYING | ROLLED_BACK | FAILED
    VERIFYING -> RESOLVED | ROLLED_BACK | FAILED
    ROLLED_BACK -> INVESTIGATING | FAILED
    RESOLVED, FAILED, CANCELLED -> (terminal; no outgoing transitions)

    Note on the direct "-> RESOLVED" edges from every pre-execution state:
    these model a real, legitimate scenario -- an external monitoring
    system (Datadog, PagerDuty, etc.) reporting that the underlying issue
    self-healed or was fixed manually OUTSIDE NemoGuard, before NemoGuard's
    own investigation/plan/execution pipeline ever reached EXECUTING. This
    is intentionally distinct from the EXECUTING/VERIFYING -> RESOLVED path
    (which represents NemoGuard's OWN verified recovery) -- callers using
    these early-exit edges MUST log an audit event that makes clear the
    incident was resolved externally, not via an executed/verified
    NemoGuard plan (see IncidentOrchestrator.process_webhook's
    INCIDENT_AUTO_RESOLVED_EXTERNALLY audit event for the canonical
    example). This is NOT a weakening of the execution/verification safety
    gate -- no capability is ever executed on this path.
    """
    
    TRANSITIONS = {
        IncidentState.DETECTED: {IncidentState.CORRELATING, IncidentState.RESOLVED},
        IncidentState.CORRELATING: {IncidentState.TRIAGING, IncidentState.FAILED, IncidentState.RESOLVED},
        IncidentState.TRIAGING: {IncidentState.INVESTIGATING, IncidentState.FAILED, IncidentState.RESOLVED},
        IncidentState.INVESTIGATING: {IncidentState.PLAN_READY, IncidentState.FAILED, IncidentState.RESOLVED},
        IncidentState.PLAN_READY: {IncidentState.AWAITING_APPROVAL, IncidentState.INVESTIGATING, IncidentState.RESOLVED},
        IncidentState.AWAITING_APPROVAL: {IncidentState.EXECUTING, IncidentState.INVESTIGATING, IncidentState.CANCELLED, IncidentState.RESOLVED},
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
