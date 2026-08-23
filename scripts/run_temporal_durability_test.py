"""
Live Temporal durability verification for a controlled read-only fixture.

This bounded integration harness uses the real Temporal server, Postgres,
production workflow implementation, lifecycle/execution activities, and public
FastAPI approval endpoint. It stubs only triage so a deterministic pre-created
one-step plan can be exercised without invoking LLM-backed investigation.

Full runs create a unique fixture, start the workflow on an isolated task
queue, wait for AWAITING_APPROVAL, deliberately shut down that active worker,
start a replacement worker on the same queue, and submit one approval through
the public API. The assertions prove the resumed workflow executes exactly one
governed read-only action and writes exactly one verification result.

Run from pipeline-copilot while Docker Compose is running:

    POSTGRES_URL='postgresql://nemoguard:nemoguard_password@localhost:5432/nemoguard_db' \
    .venv/bin/python scripts/run_temporal_durability_test.py

The fixture identifiers printed by a full run can be rechecked later without
mutation:

    DURABILITY_INCIDENT_ID=<incident-id> \
    DURABILITY_PLAN_ID=<plan-id> \
    POSTGRES_URL='postgresql://nemoguard:nemoguard_password@localhost:5432/nemoguard_db' \
    .venv/bin/python scripts/run_temporal_durability_test.py --verify-only
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# This script runs on the host; Docker service hostnames are not resolvable
# there. The caller can still override it for a non-local deployment.
os.environ.setdefault(
    "POSTGRES_URL",
    "postgresql://nemoguard:nemoguard_password@localhost:5432/nemoguard_db",
)

from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

from src.domain.activities.execution_activity import execute_plan_activity
from src.domain.activities.lifecycle_activity import (
    log_escalation_audit_event_activity,
    transition_incident_state_activity,
)
from src.domain.enums import IncidentState
from src.domain.incident_state_service import IncidentStateService
from src.domain.workflows.incident_workflow import IncidentLifecycleWorkflow
from src.store.postgres_database import PostgresDatabase


@dataclass(frozen=True)
class Fixture:
    incident_id: str
    plan_id: str
    step_id: str
    agent_run_id: str
    run_id: str


def _new_fixture() -> Fixture:
    suffix = f"{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8].upper()}"
    return Fixture(
        incident_id=f"INC-DURABILITY-RESTART-{suffix}",
        plan_id=f"PLN-DURABILITY-RESTART-{suffix}",
        step_id=f"STP-DURABILITY-RESTART-{suffix}",
        agent_run_id=f"AGR-DURABILITY-RESTART-{suffix}",
        run_id=f"RUN-DURABILITY-RESTART-{suffix}",
    )


def _fixture_from_environment() -> Fixture:
    incident_id = os.environ.get("DURABILITY_INCIDENT_ID")
    plan_id = os.environ.get("DURABILITY_PLAN_ID")
    step_id = os.environ.get("DURABILITY_STEP_ID", "")
    if not incident_id or not plan_id:
        raise RuntimeError(
            "--verify-only requires DURABILITY_INCIDENT_ID and DURABILITY_PLAN_ID "
            "from a prior full-run result."
        )
    return Fixture(
        incident_id=incident_id,
        plan_id=plan_id,
        step_id=step_id,
        agent_run_id="",
        run_id="",
    )


@activity.defn(name="triage_incident_activity")
async def precreated_plan_triage_activity(incident_id: str) -> dict:
    """Preserve the harness-created plan; all later activities are real."""
    return {"status": "EXECUTED", "saved_plan": True, "incident_id": incident_id}


def _request_json(
    url: str,
    *,
    method: str = "GET",
    token: str | None = None,
    body: dict | None = None,
) -> dict:
    payload = json.dumps(body).encode() if body is not None else None
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, data=payload, headers=headers, method=method)
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode())
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc


def _create_fixture(db: PostgresDatabase, fixture: Fixture) -> None:
    """Create the minimum FK-consistent, non-mutating plan fixture."""
    now = datetime.now(timezone.utc).isoformat()
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO incident (
                incident_id, title, summary, status, severity, primary_run_id,
                detected_at, created_at, updated_at, version
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                fixture.incident_id,
                "DURABILITY RESTART TEST — read-only approval",
                "Controlled Temporal worker restart durability fixture.",
                IncidentState.INVESTIGATING.value,
                "SEV_3",
                fixture.run_id,
                now,
                now,
                now,
                1,
            ),
        )
        conn.execute(
            """
            INSERT INTO agent_run (
                agent_run_id, incident_id, agent_name, objective, status,
                started_at, completed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                fixture.agent_run_id,
                fixture.incident_id,
                "Temporal Durability Harness",
                "Controlled worker restart validation.",
                "COMPLETED",
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO action_plan (
                action_plan_id, incident_id, agent_run_id, plan_version, status,
                overall_risk, rationale, expected_outcome, rollback_summary, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                fixture.plan_id,
                fixture.incident_id,
                fixture.agent_run_id,
                1,
                "PENDING_APPROVAL",
                "LOW",
                "Controlled read-only Temporal durability verification.",
                "No stale or partial table condition is reported.",
                "No rollback required: read-only verification.",
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO action_step (
                action_step_id, action_plan_id, sequence_no, action_type, tool_name,
                risk_level, requires_approval, parameters_json, preconditions_json,
                expected_postconditions_json, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                fixture.step_id,
                fixture.plan_id,
                1,
                "Read-only durability verification: check table staleness",
                "check_table_staleness",
                "LOW",
                0,
                json.dumps({"table_name": "order_events", "run_id": fixture.run_id}),
                "{}",
                "{}",
                "PENDING",
            ),
        )


def _assert_pristine_fixture(db: PostgresDatabase, fixture: Fixture) -> None:
    with db.get_connection() as conn:
        incident = conn.execute(
            "SELECT status FROM incident WHERE incident_id = %s",
            (fixture.incident_id,),
        ).fetchone()
        steps = conn.execute(
            """
            SELECT action_step_id, tool_name, risk_level, requires_approval, status
            FROM action_step
            WHERE action_plan_id = %s
            ORDER BY sequence_no
            """,
            (fixture.plan_id,),
        ).fetchall()
        executions = conn.execute(
            """
            SELECT COUNT(*) FROM action_execution ae
            JOIN action_step s ON s.action_step_id = ae.action_step_id
            WHERE s.action_plan_id = %s
            """,
            (fixture.plan_id,),
        ).fetchone()[0]

    expected_step = (fixture.step_id, "check_table_staleness", "LOW", 0, "PENDING")
    if not incident:
        raise RuntimeError(f"Fixture incident {fixture.incident_id} does not exist")
    if steps != [expected_step]:
        raise RuntimeError(f"Fixture does not have exactly its controlled read-only step: {steps}")
    if executions != 0:
        raise RuntimeError(f"Fixture is not pristine; expected zero action executions, found {executions}")
    if incident[0] != IncidentState.INVESTIGATING.value:
        raise RuntimeError(
            f"Fixture must begin in {IncidentState.INVESTIGATING.value}; found {incident[0]}"
        )


def _verify_terminal_database_state(db: PostgresDatabase, fixture: Fixture) -> dict:
    with db.get_connection() as conn:
        incident_status = conn.execute(
            "SELECT status FROM incident WHERE incident_id = %s",
            (fixture.incident_id,),
        ).fetchone()[0]
        plan_status = conn.execute(
            "SELECT status FROM action_plan WHERE action_plan_id = %s",
            (fixture.plan_id,),
        ).fetchone()[0]
        action_execution_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM audit_event
            WHERE incident_id = %s AND event_type = 'ACTION_EXECUTED'
            """,
            (fixture.incident_id,),
        ).fetchone()[0]
        verification_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM verification_result
            WHERE incident_id = %s AND action_plan_id = %s AND status = 'PASSED'
            """,
            (fixture.incident_id, fixture.plan_id),
        ).fetchone()[0]
        persisted_execution_count = conn.execute(
            """
            SELECT COUNT(*) FROM action_execution ae
            JOIN action_step s ON s.action_step_id = ae.action_step_id
            WHERE s.action_plan_id = %s
            """,
            (fixture.plan_id,),
        ).fetchone()[0]
        steps = conn.execute(
            """
            SELECT tool_name, risk_level, requires_approval, status
            FROM action_step
            WHERE action_plan_id = %s
            ORDER BY sequence_no
            """,
            (fixture.plan_id,),
        ).fetchall()

    if action_execution_count != 1:
        raise AssertionError(
            f"Expected exactly one governed ACTION_EXECUTED audit event, found {action_execution_count}"
        )
    if persisted_execution_count != 1:
        raise AssertionError(
            f"Expected exactly one action_execution record, found {persisted_execution_count}"
        )
    if verification_count != 1:
        raise AssertionError(f"Expected exactly one passed verification result, found {verification_count}")
    if len(steps) != 1 or steps[0][0] != "check_table_staleness" or steps[0][1] != "LOW":
        raise AssertionError(f"Expected exactly one LOW-risk read-only action, found {steps}")
    if steps[0][3] != "SUCCEEDED":
        raise AssertionError(f"Read-only step did not succeed: {steps}")
    if incident_status != IncidentState.RESOLVED.value:
        raise AssertionError(f"Expected resolved terminal incident state, found {incident_status}")
    if plan_status != "EXECUTED":
        raise AssertionError(f"Expected EXECUTED terminal plan state, found {plan_status}")

    return {
        "incident_status": incident_status,
        "plan_status": plan_status,
        "action_execution_count": action_execution_count,
        "persisted_execution_count": persisted_execution_count,
        "verification_count": verification_count,
        "step": {
            "tool_name": steps[0][0],
            "risk_level": steps[0][1],
            "requires_approval": steps[0][2],
            "status": steps[0][3],
        },
    }


async def _wait_for_state(
    db: PostgresDatabase,
    incident_id: str,
    expected: IncidentState,
    *,
    timeout_seconds: float = 15,
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT status FROM incident WHERE incident_id = %s",
                (incident_id,),
            ).fetchone()
        if row and row[0] == expected.value:
            return
        await asyncio.sleep(0.1)
    raise TimeoutError(f"Workflow did not reach {expected.value} within {timeout_seconds} seconds")


def _worker(client: Client, task_queue: str) -> Worker:
    return Worker(
        client,
        task_queue=task_queue,
        workflows=[IncidentLifecycleWorkflow],
        activities=[
            precreated_plan_triage_activity,
            transition_incident_state_activity,
            execute_plan_activity,
            log_escalation_audit_event_activity,
        ],
    )


async def main() -> None:
    api_base_url = os.getenv("NEMOGUARD_API_URL", "http://localhost:8000").rstrip("/")
    temporal_url = os.getenv("TEMPORAL_URL", "localhost:7233")
    db = PostgresDatabase(os.environ["POSTGRES_URL"])
    fixture = _new_fixture()
    _create_fixture(db, fixture)
    _assert_pristine_fixture(db, fixture)

    # Setup only: use the real service to make the workflow's subsequent
    # PLAN_READY -> AWAITING_APPROVAL state transition legal and auditable.
    IncidentStateService(db).transition(
        incident_id=fixture.incident_id,
        to=IncidentState.PLAN_READY,
        actor="TEMPORAL_DURABILITY_HARNESS",
        reason="Controlled setup for isolated Temporal worker restart validation.",
    )

    task_queue = f"temporal-durability-restart-{uuid.uuid4().hex[:10]}"
    client = await Client.connect(temporal_url)
    handle = None

    # Start the workflow on worker A and interrupt that worker only after the
    # persisted approval wait is active. Its workflow state remains in the
    # real Temporal service; worker B below must resume it.
    async with _worker(client, task_queue):
        handle = await client.start_workflow(
            IncidentLifecycleWorkflow.run,
            fixture.incident_id,
            id=f"incident-{fixture.incident_id}",
            task_queue=task_queue,
        )
        await _wait_for_state(db, fixture.incident_id, IncidentState.AWAITING_APPROVAL)

    # Exiting the worker context removes all polling workers from this
    # isolated queue. Keep the workflow durable and unsignaled briefly before
    # recreating a worker, proving the pending approval wait is server-backed.
    await asyncio.sleep(0.5)

    async with _worker(client, task_queue):
        approver_token = _request_json(
            f"{api_base_url}/api/v2/auth/mock-login?role=approver"
        )["access_token"]
        plans = _request_json(
            f"{api_base_url}/api/v2/incidents/{fixture.incident_id}/plans",
            token=approver_token,
        )
        plan = next(
            (candidate for candidate in plans if candidate["action_plan_id"] == fixture.plan_id),
            None,
        )
        if not plan:
            raise RuntimeError(f"Controlled plan {fixture.plan_id} was not returned by the API")

        approval_response = _request_json(
            f"{api_base_url}/api/v2/incidents/{fixture.incident_id}/plans/{fixture.plan_id}/approve",
            method="POST",
            token=approver_token,
            body={"decision": "APPROVED", "plan_hash": plan["plan_hash"]},
        )
        if approval_response.get("status") != "signaled_temporal":
            raise AssertionError(f"Approval was not delivered through Temporal: {approval_response}")

        result = await handle.result()
        if result != {"status": "completed", "action": "executed"}:
            raise AssertionError(f"Unexpected workflow result: {result}")

    verification = _verify_terminal_database_state(db, fixture)
    print(
        json.dumps(
            {
                "fixture": {
                    "incident_id": fixture.incident_id,
                    "plan_id": fixture.plan_id,
                    "step_id": fixture.step_id,
                },
                "worker_restart": {
                    "first_worker_stopped_at": IncidentState.AWAITING_APPROVAL.value,
                    "replacement_worker_started": True,
                },
                "workflow_result": result,
                "approval_response": approval_response,
                "verification": verification,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["--verify-only"]:
        fixture = _fixture_from_environment()
        verification = _verify_terminal_database_state(
            PostgresDatabase(os.environ["POSTGRES_URL"]), fixture
        )
        print(
            json.dumps(
                {
                    "fixture": {
                        "incident_id": fixture.incident_id,
                        "plan_id": fixture.plan_id,
                    },
                    "verification": verification,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        asyncio.run(main())
