"""
IncidentStateService -- the single authoritative gateway for changing an
incident's lifecycle status.

Per docs/NemoGuard_Enterprise_Hardening_and_Productization_Build_Plan.md
Priority 3 ("Enforce the State Machine"): prior to this module, incident
status was mutated via ad hoc UPDATE incident SET status = ... statements
scattered across orchestrator.py and api/main.py, with no validation
against StateMachine.TRANSITIONS, no row locking (so two concurrent
writers could race), and no guaranteed audit trail per transition.

This service is now the ONLY code path that may write to incident.status.
It:
  1. Locks the incident row (SELECT ... FOR UPDATE) inside a transaction.
  2. Loads the current status.
  3. Validates the requested transition against StateMachine.TRANSITIONS.
  4. Applies the status update (plus any additional columns that must
     change atomically with the transition, e.g. resolved_at).
  5. Increments the optimistic-lock `version` column.
  6. Inserts an INCIDENT_STATE_CHANGED audit event capturing from/to/actor/
     reason.
  7. Commits (via the underlying PostgresDatabase.get_connection()
     context manager, which commits on successful exit / rolls back on
     exception).

Terminal states (RESOLVED, FAILED, CANCELLED) have no outgoing transitions
in StateMachine.TRANSITIONS, so any attempt to move out of them will raise
InvalidTransitionError -- reopening a terminal incident must go through an
explicit, separate "reopen" flow (not yet implemented), not a silent status
overwrite.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from src.domain.enums import IncidentState
from src.domain.state_machine import StateMachine, InvalidTransitionError
from src.store.postgres_database import PostgresDatabase


class IncidentNotFoundError(Exception):
    pass


class IncidentStateService:
    """
    Authoritative service for incident lifecycle transitions.

    Usage:
        service = IncidentStateService(db)
        service.transition(
            incident_id="INC-...",
            to=IncidentState.INVESTIGATING,
            actor="System",
            reason="Webhook created a new incident and started investigation.",
        )
    """

    def __init__(self, db: PostgresDatabase):
        self.db = db

    def _generate_audit_id(self) -> str:
        return f"AUD-{uuid.uuid4().hex[:8]}"

    def get_current_state(self, incident_id: str) -> IncidentState:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT status FROM incident WHERE incident_id = %s", (incident_id,)
            )
            row = cursor.fetchone()
            if not row:
                raise IncidentNotFoundError(f"Incident {incident_id} not found")
            return IncidentState(row[0])

    def transition(
        self,
        *,
        incident_id: str,
        to: IncidentState,
        actor: str = "SYSTEM",
        reason: str = "",
        expected_from: Optional[IncidentState] = None,
        extra_columns: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Perform a validated, audited, row-locked incident state transition.

        Args:
            incident_id: the incident to transition.
            to: the target IncidentState.
            actor: human-readable actor identifier for the audit event
                (e.g. "Watcher Agent", "Commander", a user_id, "SYSTEM").
            reason: free-text explanation persisted in the audit event
                summary -- should describe WHY the transition happened.
            expected_from: optional optimistic-concurrency guard. If
                provided and the incident's current status does not match,
                raises InvalidTransitionError even if the state machine
                would otherwise allow this transition -- protects against
                acting on stale data.
            extra_columns: optional dict of additional incident columns to
                set atomically with the status change (e.g.
                {"resolved_at": now_iso}). Column names are NOT validated
                against a fixed allowlist here; callers are internal/trusted
                domain code, not user input.

        Returns:
            {"from": <old status value>, "to": <new status value>, "incident_id": ...}

        Raises:
            IncidentNotFoundError: incident_id does not exist.
            InvalidTransitionError: transition is not permitted by the
                state machine, or expected_from did not match reality.
        """
        now = datetime.now(timezone.utc).isoformat()

        with self.db.get_connection() as conn:
            # Lock the row for the duration of this transaction so a
            # concurrent transition attempt on the same incident cannot
            # interleave with this one (prevents lost-update races on the
            # status/version columns).
            cursor = conn.execute(
                "SELECT status, version FROM incident WHERE incident_id = %s FOR UPDATE",
                (incident_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise IncidentNotFoundError(f"Incident {incident_id} not found")

            current_status_raw, current_version = row[0], row[1]
            current_state = IncidentState(current_status_raw)

            if expected_from is not None and current_state != expected_from:
                raise InvalidTransitionError(
                    f"Expected incident {incident_id} to be in state "
                    f"{expected_from.value}, but it is actually in "
                    f"{current_state.value}. Refusing transition to avoid "
                    f"acting on stale state."
                )

            # This is the actual enforcement point: validates against
            # StateMachine.TRANSITIONS and raises InvalidTransitionError on
            # any disallowed move (including self-transitions and moves out
            # of terminal states).
            StateMachine.validate_transition(current_state.value, to.value)

            set_clauses = ["status = %s", "updated_at = %s", "version = version + 1"]
            params = [to.value, now]

            if extra_columns:
                for col, val in extra_columns.items():
                    set_clauses.append(f"{col} = %s")
                    params.append(val)

            params.append(incident_id)
            conn.execute(
                f"UPDATE incident SET {', '.join(set_clauses)} WHERE incident_id = %s",
                tuple(params),
            )

            summary = (
                f"Incident transitioned {current_state.value} -> {to.value}"
                + (f": {reason}" if reason else "")
            )
            conn.execute(
                """
                INSERT INTO audit_event (audit_event_id, incident_id, actor_type, actor_id, event_type, event_summary, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    self._generate_audit_id(),
                    incident_id,
                    "SYSTEM",
                    actor,
                    "INCIDENT_STATE_CHANGED",
                    summary,
                    now,
                ),
            )

        return {
            "incident_id": incident_id,
            "from": current_state.value,
            "to": to.value,
        }
