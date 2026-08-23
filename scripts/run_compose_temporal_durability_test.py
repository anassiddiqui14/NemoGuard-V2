"""
Container-topology durability test for the deployed Compose Temporal worker.

This is deliberately separate from run_temporal_durability_test.py. It stops
and recreates the actual `nemoguard-temporal-worker` container after a workflow
has reached AWAITING_APPROVAL on `incident-task-queue`.

Safety guard:
  The container must already have been launched with
  NEMOGUARD_PRECREATED_PLAN_TRIAGE=1. That default-off staging-only mode
  preserves the controlled pre-created read-only plan while keeping the
  production workflow, production queue, FastAPI approval boundary, Temporal
  server, lifecycle/execution activities, governed capability execution, and
  Postgres persistence real.

From pipeline-copilot:

  NEMOGUARD_PRECREATED_PLAN_TRIAGE=1 docker compose up -d --build --force-recreate temporal-worker
  POSTGRES_URL='postgresql://nemoguard:nemoguard_password@localhost:5432/nemoguard_db' \
  PYTHONPATH=. .venv/bin/python scripts/run_compose_temporal_durability_test.py

Restore normal worker triage after the test:

  NEMOGUARD_PRECREATED_PLAN_TRIAGE=0 docker compose up -d --force-recreate temporal-worker
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault(
    "POSTGRES_URL",
    "postgresql://nemoguard:nemoguard_password@localhost:5432/nemoguard_db",
)

from temporalio.client import Client

from scripts.run_temporal_durability_test import (
    Fixture,
    _create_fixture,
    _new_fixture,
    _request_json,
    _verify_terminal_database_state,
    _wait_for_state,
)
from src.domain.enums import IncidentState
from src.domain.incident_state_service import IncidentStateService
from src.domain.workflows.incident_workflow import IncidentLifecycleWorkflow
from src.store.postgres_database import PostgresDatabase

COMPOSE_WORKER_CONTAINER = "nemoguard-temporal-worker"
PRODUCTION_TASK_QUEUE = "incident-task-queue"


def _run_docker(*args: str) -> str:
    completed = subprocess.run(
        ["docker", *args],
        cwd=PROJECT_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout.strip()


def _require_staging_worker() -> None:
    environment = _run_docker(
        "inspect",
        "--format",
        "{{range .Config.Env}}{{println .}}{{end}}",
        COMPOSE_WORKER_CONTAINER,
    )
    if "NEMOGUARD_PRECREATED_PLAN_TRIAGE=1" not in environment.splitlines():
        raise RuntimeError(
            "Refusing to start a controlled fixture on the production queue: "
            f"{COMPOSE_WORKER_CONTAINER} is not running with "
            "NEMOGUARD_PRECREATED_PLAN_TRIAGE=1. Recreate it explicitly in "
            "the default-off staging mode first."
        )


def _container_is_running() -> bool:
    return (
        _run_docker(
            "inspect",
            "--format",
            "{{.State.Running}}",
            COMPOSE_WORKER_CONTAINER,
        )
        == "true"
    )


async def main() -> None:
    _require_staging_worker()

    api_base_url = os.getenv("NEMOGUARD_API_URL", "http://localhost:8000").rstrip("/")
    temporal_url = os.getenv("TEMPORAL_URL", "localhost:7233")
    db = PostgresDatabase(os.environ["POSTGRES_URL"])
    fixture: Fixture = _new_fixture()
    _create_fixture(db, fixture)

    IncidentStateService(db).transition(
        incident_id=fixture.incident_id,
        to=IncidentState.PLAN_READY,
        actor="COMPOSE_DURABILITY_HARNESS",
        reason="Controlled setup for deployed Compose worker restart validation.",
    )

    client = await Client.connect(temporal_url)
    handle = await client.start_workflow(
        IncidentLifecycleWorkflow.run,
        fixture.incident_id,
        id=f"incident-{fixture.incident_id}",
        task_queue=PRODUCTION_TASK_QUEUE,
    )
    await _wait_for_state(db, fixture.incident_id, IncidentState.AWAITING_APPROVAL)

    # This is the topology proof: stop the actual deployed worker container
    # only after the server-persisted wait has become active.
    _run_docker("compose", "stop", "temporal-worker")
    if _container_is_running():
        raise AssertionError("Compose worker container is still running after docker compose stop")

    # The workflow must remain durable while no worker polls the production
    # queue. A direct DB assertion confirms the lifecycle did not regress.
    await asyncio.sleep(0.5)
    await _wait_for_state(db, fixture.incident_id, IncidentState.AWAITING_APPROVAL)

    _run_docker("compose", "up", "-d", "temporal-worker")

    # Wait for the replacement container to be running before signaling; the
    # API signal itself is persisted by Temporal, while the resumed workflow
    # must be handled by this recreated production container.
    deadline = asyncio.get_running_loop().time() + 30
    while asyncio.get_running_loop().time() < deadline:
        if _container_is_running():
            break
        await asyncio.sleep(0.2)
    else:
        raise TimeoutError("Replacement Compose temporal worker did not become running")

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
                "compose_worker_restart": {
                    "container": COMPOSE_WORKER_CONTAINER,
                    "first_container_stopped_at": IncidentState.AWAITING_APPROVAL.value,
                    "replacement_container_running": True,
                },
                "approval_response": approval_response,
                "workflow_result": result,
                "verification": verification,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
