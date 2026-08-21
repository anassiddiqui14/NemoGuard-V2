"""
Cross-tenant isolation integration tests (build plan Priority 8 / spec
§12.5): explicit proof that incident ID enumeration cannot cross tenant
boundaries, exercised against the REAL running API service (over HTTP,
same pattern as scripts/test_wp005_roles.py) + a real PostgreSQL database.

Per spec §12.5, these tests specifically prove:
  - incident ID enumeration cannot cross tenant
  - a user in tenant A cannot read tenant B's incident sub-resources
    (evidence, plans, events) even when they know the exact incident_id
  - tenant isolation holds even for a fully-privileged (admin) role

Skips gracefully if no reachable API/PostgreSQL is configured, so it does
not fail a plain `pytest tests/` run with no services up -- run
`docker compose up` first, then TEST_API_BASE_URL (default
http://localhost:8000) and TEST_POSTGRES_URL/POSTGRES_URL must be
reachable.
"""

import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests

from src.store.postgres_database import PostgresDatabase

POSTGRES_URL = os.environ.get(
    "TEST_POSTGRES_URL",
    os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@localhost:5432/nemoguard_db"),
)
API_BASE_URL = os.environ.get("TEST_API_BASE_URL", "http://localhost:8000")


def _postgres_available() -> bool:
    try:
        db = PostgresDatabase(POSTGRES_URL)
        with db.get_connection() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def _api_available() -> bool:
    try:
        resp = requests.get(f"{API_BASE_URL}/api/v2/status", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not (_postgres_available() and _api_available()),
    reason="Requires a reachable Postgres AND a running API service (start `docker compose up` to run this test).",
)


@pytest.fixture
def db():
    return PostgresDatabase(POSTGRES_URL)


@pytest.fixture
def tenant_a_incident(db):
    """A real incident row belonging to tenant_a_isolation_test, with a real evidence row attached."""
    incident_id = f"TEST-INC-A-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO incident (incident_id, title, status, severity, detected_at, created_at, updated_at, version, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (incident_id, "Tenant A test incident", "INVESTIGATING", "SEV_3", now, now, now, 1, "tenant_a_isolation_test"),
        )
        conn.execute(
            """
            INSERT INTO agent_run (agent_run_id, incident_id, agent_name, objective, status)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (agent_run_id) DO NOTHING
            """,
            ("SYSTEM", incident_id, "System Triage", "Test", "COMPLETED"),
        )
        conn.execute(
            """
            INSERT INTO evidence (evidence_id, incident_id, evidence_type, source_system, title, excerpt, collected_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (f"EVD-{uuid.uuid4().hex[:8]}", incident_id, "Log", "TestSystem", "Secret Tenant A Evidence", "sensitive content", now),
        )
    yield incident_id
    with db.get_connection() as conn:
        conn.execute("DELETE FROM evidence WHERE incident_id = %s", (incident_id,))
        conn.execute("DELETE FROM audit_event WHERE incident_id = %s", (incident_id,))
        conn.execute("DELETE FROM incident WHERE incident_id = %s", (incident_id,))


def _token_for_tenant(tenant_id: str) -> str:
    """
    Mints a real, correctly-signed JWT for an arbitrary tenant by calling
    the SAME create_access_token() the API itself uses, ensuring the token
    is byte-for-byte what a real login would produce -- no mocking of the
    API's own auth internals.
    """
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
    from src.api.auth import create_access_token

    return create_access_token(
        data={
            "sub": f"test-user-{tenant_id}",
            "email": f"user@{tenant_id}.example.com",
            "roles": ["admin"],  # even admin -- tenant isolation must hold regardless of role
            "tenant_id": tenant_id,
            "workspace_id": "ws_test",
        },
        expires_delta=timedelta(hours=1),
    )


class TestCrossTenantIsolation:
    def test_tenant_b_cannot_read_tenant_a_incident_directly(self, tenant_a_incident):
        tenant_b_token = _token_for_tenant("tenant_b_isolation_test")
        resp = requests.get(
            f"{API_BASE_URL}/api/v2/incidents/{tenant_a_incident}",
            headers={"Authorization": f"Bearer {tenant_b_token}"},
        )
        # 404, not 403 -- must not confirm the incident exists in another tenant.
        assert resp.status_code == 404

    def test_tenant_a_can_read_its_own_incident(self, tenant_a_incident):
        tenant_a_token = _token_for_tenant("tenant_a_isolation_test")
        resp = requests.get(
            f"{API_BASE_URL}/api/v2/incidents/{tenant_a_incident}",
            headers={"Authorization": f"Bearer {tenant_a_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["incident_id"] == tenant_a_incident

    def test_tenant_b_cannot_enumerate_tenant_a_incident_in_list(self, tenant_a_incident):
        tenant_b_token = _token_for_tenant("tenant_b_isolation_test")
        resp = requests.get(
            f"{API_BASE_URL}/api/v2/incidents?state=all",
            headers={"Authorization": f"Bearer {tenant_b_token}"},
        )
        assert resp.status_code == 200
        ids = [i["incident_id"] for i in resp.json()]
        assert tenant_a_incident not in ids

    def test_tenant_b_cannot_read_tenant_a_evidence_even_knowing_the_id(self, tenant_a_incident):
        """
        The core sub-resource leak this WP closes: knowing a valid
        incident_id from another tenant must NOT unlock its evidence,
        even though the /evidence endpoint only ever filtered by
        incident_id before this fix.
        """
        tenant_b_token = _token_for_tenant("tenant_b_isolation_test")
        resp = requests.get(
            f"{API_BASE_URL}/api/v2/incidents/{tenant_a_incident}/evidence",
            headers={"Authorization": f"Bearer {tenant_b_token}"},
        )
        assert resp.status_code == 404

    def test_tenant_a_can_read_its_own_evidence(self, tenant_a_incident):
        tenant_a_token = _token_for_tenant("tenant_a_isolation_test")
        resp = requests.get(
            f"{API_BASE_URL}/api/v2/incidents/{tenant_a_incident}/evidence",
            headers={"Authorization": f"Bearer {tenant_a_token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["title"] == "Secret Tenant A Evidence"

    def test_tenant_b_cannot_read_tenant_a_plans(self, tenant_a_incident):
        tenant_b_token = _token_for_tenant("tenant_b_isolation_test")
        resp = requests.get(
            f"{API_BASE_URL}/api/v2/incidents/{tenant_a_incident}/plans",
            headers={"Authorization": f"Bearer {tenant_b_token}"},
        )
        assert resp.status_code == 404

    def test_tenant_b_cannot_read_tenant_a_events(self, tenant_a_incident):
        tenant_b_token = _token_for_tenant("tenant_b_isolation_test")
        resp = requests.get(
            f"{API_BASE_URL}/api/v2/incidents/{tenant_a_incident}/events",
            headers={"Authorization": f"Bearer {tenant_b_token}"},
        )
        assert resp.status_code == 404

    def test_tenant_b_cannot_trigger_triage_on_tenant_a_incident(self, tenant_a_incident):
        """Admin in tenant B still cannot mutate tenant A's incident -- proves
        tenant isolation holds even for a fully-privileged role."""
        tenant_b_token = _token_for_tenant("tenant_b_isolation_test")
        resp = requests.post(
            f"{API_BASE_URL}/api/v2/incidents/{tenant_a_incident}/triage",
            headers={"Authorization": f"Bearer {tenant_b_token}"},
        )
        assert resp.status_code == 404

    def test_tenant_b_cannot_stream_tenant_a_sse_events(self, tenant_a_incident):
        tenant_b_token = _token_for_tenant("tenant_b_isolation_test")
        resp = requests.get(
            f"{API_BASE_URL}/api/v2/incidents/{tenant_a_incident}/events/stream?token={tenant_b_token}",
            timeout=3,
        )
        assert resp.status_code == 404
