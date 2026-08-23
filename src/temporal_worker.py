import asyncio
import os
import logging
from temporalio.client import Client
from temporalio.worker import Worker

from src.domain.workflows.incident_workflow import IncidentLifecycleWorkflow
from temporalio import activity

from src.domain.activities.triage_activity import triage_incident_activity
from src.domain.activities.execution_activity import execute_plan_activity
from src.domain.activities.lifecycle_activity import (
    transition_incident_state_activity,
    log_escalation_audit_event_activity,
)

logging.basicConfig(level=logging.INFO)


@activity.defn(name="triage_incident_activity")
async def staging_precreated_plan_triage_activity(incident_id: str) -> dict:
    """
    Opt-in staging-only triage substitute for container restart validation.

    This is registered only when NEMOGUARD_PRECREATED_PLAN_TRIAGE=1. The
    harness creates the controlled plan before the workflow begins, so calling
    LLM-backed triage would replace that plan and invalidate the exact-once
    assertion. The workflow, approval boundary, lifecycle, governed
    execution, verification, and persistence paths remain production code.
    """
    return {"status": "EXECUTED", "saved_plan": True, "incident_id": incident_id}


async def main():
    temporal_url = os.getenv("TEMPORAL_URL", "localhost:7233")
    logging.info(f"Connecting to Temporal server at {temporal_url}")
    
    # Create client connected to server at the given address
    client = await Client.connect(temporal_url)

    staging_precreated_plan = os.getenv("NEMOGUARD_PRECREATED_PLAN_TRIAGE", "0") == "1"
    triage_activity = (
        staging_precreated_plan_triage_activity
        if staging_precreated_plan
        else triage_incident_activity
    )
    if staging_precreated_plan:
        logging.warning(
            "Starting opt-in staging worker with pre-created-plan triage substitute; "
            "do not use this mode in production."
        )

    # Run the worker. The queue remains the production queue so the test also
    # verifies the actual deployed worker container's polling/restart path.
    worker = Worker(
        client,
        task_queue="incident-task-queue",
        workflows=[IncidentLifecycleWorkflow],
        activities=[
            triage_activity,
            execute_plan_activity,
            transition_incident_state_activity,
            log_escalation_audit_event_activity,
        ],
    )
    logging.info("Starting Temporal Worker...")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
