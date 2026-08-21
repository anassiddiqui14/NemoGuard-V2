from temporalio import activity
from src.store.postgres_database import PostgresDatabase
from src.domain.incident_state_service import IncidentStateService, IncidentNotFoundError
from src.domain.state_machine import InvalidTransitionError
from src.domain.enums import IncidentState
import os


def _get_db() -> PostgresDatabase:
    return PostgresDatabase(
        os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db")
    )


@activity.defn
async def transition_incident_state_activity(payload: dict) -> dict:
    """
    Temporal Activity wrapping IncidentStateService.transition().

    Workflows cannot perform I/O (DB writes) directly per Temporal's
    determinism rules -- every incident lifecycle state change the
    workflow needs to make (entering AWAITING_APPROVAL, escalating on
    timeout, cancelling) must go through an Activity, not a bare function
    call inside `run()`. This activity is the shared, reusable wrapper for
    all such transitions, so the workflow itself stays free of any direct
    database access.

    `payload` keys: incident_id, to (IncidentState value string), actor,
    reason.
    """
    incident_id = payload["incident_id"]
    to = IncidentState(payload["to"])
    actor = payload.get("actor", "TEMPORAL_WORKFLOW")
    reason = payload.get("reason", "")

    db = _get_db()
    state_service = IncidentStateService(db)
    try:
        result = state_service.transition(incident_id=incident_id, to=to, actor=actor, reason=reason)
        return {"status": "ok", "result": result}
    except IncidentNotFoundError:
        activity.logger.warning(f"transition_incident_state_activity: incident {incident_id} not found.")
        return {"status": "not_found"}
    except InvalidTransitionError as e:
        # Not every workflow-driven transition attempt is guaranteed to
        # still be legal by the time it runs (e.g. a human already cancelled
        # the incident through a completely different path while the
        # workflow was mid-timeout-wait). Log and continue rather than
        # crashing the workflow over a transition that simply no longer
        # applies.
        activity.logger.warning(f"transition_incident_state_activity: invalid transition for {incident_id}: {e}")
        return {"status": "invalid_transition", "detail": str(e)}


@activity.defn
async def log_escalation_audit_event_activity(payload: dict) -> dict:
    """
    Records an INCIDENT_ESCALATED audit event when the workflow's approval
    wait times out (build plan Priority 10 section 14.4: "escalation
    timeout"). Kept as its own small activity (rather than folded into
    transition_incident_state_activity) so it can be called even when no
    state transition is appropriate/legal at that moment -- the escalation
    record itself is the important side effect, independent of whatever
    state the incident happens to be in.
    """
    import uuid
    from datetime import datetime, timezone

    incident_id = payload["incident_id"]
    summary = payload.get("summary", "Approval wait timed out; escalated for human attention.")

    db = _get_db()
    now = datetime.now(timezone.utc).isoformat()
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO audit_event (audit_event_id, incident_id, actor_type, actor_id, event_type, event_summary, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (f"AUD-{uuid.uuid4().hex[:8]}", incident_id, "SYSTEM", "TEMPORAL_WORKFLOW", "INCIDENT_ESCALATED", summary, now),
        )
    return {"status": "ok"}
