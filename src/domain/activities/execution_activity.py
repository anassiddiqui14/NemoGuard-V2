from temporalio import activity
from src.domain.orchestrator import IncidentOrchestrator
import asyncio

@activity.defn
async def execute_plan_activity(args: dict) -> dict:
    """
    Temporal Activity that executes an approved recovery plan.
    args: {"incident_id": str, "plan_id": str}
    """
    incident_id = args.get("incident_id")
    plan_id = args.get("plan_id")
    activity.logger.info(f"Starting execution activity for incident {incident_id}, plan {plan_id}")
    
    orchestrator = IncidentOrchestrator()
    loop = asyncio.get_running_loop()
    # execute_plan is synchronous. Preserve its governed outcome for the
    # workflow: MANUAL_ACTION_REQUIRED must not be reported as successful
    # execution simply because the activity itself completed normally.
    result = await loop.run_in_executor(None, orchestrator.execute_plan, incident_id, plan_id)

    activity.logger.info(
        f"Completed execution activity for incident {incident_id} with status={result.get('status')}"
    )
    return result
