import asyncio
import os
import logging
from temporalio.client import Client
from temporalio.worker import Worker

from src.domain.workflows.incident_workflow import IncidentLifecycleWorkflow
from src.domain.activities.triage_activity import triage_incident_activity
from src.domain.activities.execution_activity import execute_plan_activity
from src.domain.activities.lifecycle_activity import (
    transition_incident_state_activity,
    log_escalation_audit_event_activity,
)

logging.basicConfig(level=logging.INFO)

async def main():
    temporal_url = os.getenv("TEMPORAL_URL", "localhost:7233")
    logging.info(f"Connecting to Temporal server at {temporal_url}")
    
    # Create client connected to server at the given address
    client = await Client.connect(temporal_url)

    # Run the worker
    worker = Worker(
        client,
        task_queue="incident-task-queue",
        workflows=[IncidentLifecycleWorkflow],
        activities=[
            triage_incident_activity,
            execute_plan_activity,
            transition_incident_state_activity,
            log_escalation_audit_event_activity,
        ],
    )
    logging.info("Starting Temporal Worker...")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
