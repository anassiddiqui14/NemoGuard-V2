"""
Integration test for IncidentStateService against a REAL PostgreSQL
database (the running `nemoguard-postgres` container from docker-compose).

Per docs/NemoGuard_Enterprise_Hardening_and_Productization_Build_Plan.md
WP-001 item 9: "Add an integration test proving invalid transitions are
rejected."

Skips gracefully (rather than failing) if no reachable Postgres instance is
configured -- this test is meant to run against the local dev stack
(`docker compose up`) or a CI service container exposing the same
POSTGRES_URL default.
"""

import os
import uuid
from datetime import datetime, timezone

import pytest

from src.domain.enums import IncidentState
from src.domain.incident_state_service import IncidentStateService, IncidentNotFoundError
from src.domain.state_machine import InvalidTransitionError
from src.store.postgres_database import PostgresDatabase


POSTGRES_URL = os.environ.get(
    "TEST_POSTGRES_URL",
    os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@localhost:5432/nemoguard_db"),
)


def _postgres_available() -> bool:
    try:
        db = PostgresDatabase(POSTGRES_URL)
        with db.get_connection() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_available(),
    reason="No reachable PostgreSQL instance at TEST_POSTGRES_URL/POSTGRES_URL (start `docker compose up postgres` to run this test).",
)


@pytest.fixture
def db():
    return PostgresDatabase(POSTGRES_URL)


@pytest.fixture
def state_service(db):
    return IncidentStateService(db)


@pytest.fixture
def test_incident(db):
    """Creates a minimal real incident row in DETECTED state, cleans it up after the test."""
    incident_id = f"TEST-INC-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO incident (incident_id, title, status, severity, detected_at, created_at, updated_at, version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (incident_id, "Test incident for state service", IncidentState.DETECTED.value, "SEV_3", now, now, now, 1),
        )
    yield incident_id
    with db.get_connection() as conn:
        conn.execute("DELETE FROM audit_event WHERE incident_id = %s", (incident_id,))
        conn.execute("DELETE FROM incident WHERE incident_id = %s", (incident_id,))


class TestIncidentStateServiceIntegration:
    def test_valid_transition_updates_status_and_logs_audit_event(self, state_service, db, test_incident):
        result = state_service.transition(
            incident_id=test_incident,
            to=IncidentState.CORRELATING,
            actor="test-suite",
            reason="integration test valid transition",
        )
        assert result["from"] == IncidentState.DETECTED.value
        assert result["to"] == IncidentState.CORRELATING.value

        assert state_service.get_current_state(test_incident) == IncidentState.CORRELATING

        with db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT event_type, actor_id FROM audit_event WHERE incident_id = %s AND event_type = 'INCIDENT_STATE_CHANGED'",
                (test_incident,),
            )
            rows = cursor.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "INCIDENT_STATE_CHANGED"
        assert rows[0][1] == "test-suite"

    def test_invalid_transition_is_rejected_and_does_not_mutate_state(self, state_service, db, test_incident):
        # DETECTED -> EXECUTING is not a legal transition.
        with pytest.raises(InvalidTransitionError):
            state_service.transition(
                incident_id=test_incident,
                to=IncidentState.EXECUTING,
                actor="test-suite",
                reason="should be rejected",
            )

        # Status must remain unchanged (DETECTED), and no audit event should have been written.
        assert state_service.get_current_state(test_incident) == IncidentState.DETECTED
        with db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM audit_event WHERE incident_id = %s AND event_type = 'INCIDENT_STATE_CHANGED'",
                (test_incident,),
            )
            count = cursor.fetchone()[0]
        assert count == 0

    def test_expected_from_mismatch_is_rejected(self, state_service, test_incident):
        with pytest.raises(InvalidTransitionError):
            state_service.transition(
                incident_id=test_incident,
                to=IncidentState.CORRELATING,
                actor="test-suite",
                reason="stale expectation",
                expected_from=IncidentState.INVESTIGATING,  # incident is actually DETECTED
            )
        assert state_service.get_current_state(test_incident) == IncidentState.DETECTED

    def test_transition_on_nonexistent_incident_raises_not_found(self, state_service):
        with pytest.raises(IncidentNotFoundError):
            state_service.transition(
                incident_id="TEST-INC-DOES-NOT-EXIST-00000000",
                to=IncidentState.RESOLVED,
                actor="test-suite",
            )

    def test_terminal_state_cannot_transition_further(self, state_service, test_incident):
        # Reach a terminal state via a legal path.
        state_service.transition(incident_id=test_incident, to=IncidentState.CORRELATING, actor="t")
        state_service.transition(incident_id=test_incident, to=IncidentState.FAILED, actor="t")
        assert state_service.get_current_state(test_incident) == IncidentState.FAILED

        with pytest.raises(InvalidTransitionError):
            state_service.transition(incident_id=test_incident, to=IncidentState.INVESTIGATING, actor="t")
