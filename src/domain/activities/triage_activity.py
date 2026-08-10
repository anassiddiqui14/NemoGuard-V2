from temporalio import activity
from src.domain.orchestrator import IncidentOrchestrator
import asyncio

@activity.defn
async def triage_incident_activity(incident_id: str) -> dict:
    """
    Temporal Activity that wraps the LangGraph execution for incident triage.
    """
    activity.logger.info(f"Starting triage activity for incident {incident_id}")
    orchestrator = IncidentOrchestrator()
    
    # We use run_in_executor because triage_incident runs synchronous DB queries 
    # and calls asyncio.run inside it.
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, orchestrator.triage_incident, incident_id)
    
    activity.logger.info(f"Completed triage activity for incident {incident_id}: {result}")
    return result
