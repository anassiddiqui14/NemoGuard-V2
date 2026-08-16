from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
from typing import Dict, Any

with workflow.unsafe.imports_passed_through():
    from src.domain.activities.triage_activity import triage_incident_activity
    from src.domain.activities.execution_activity import execute_plan_activity

@workflow.defn
class IncidentLifecycleWorkflow:
    def __init__(self):
        self.approval_decision = None
        self.plan_id = None

    @workflow.run
    async def run(self, incident_id: str) -> dict:
        workflow.logger.info(f"Started IncidentLifecycleWorkflow for {incident_id}")
        
        # 1. Run Triage Activity (Investigate and generate plan)
        # The full multi-agent chain (RCA -> Impact -> Runbook -> Grounding
        # Critic, each doing several tool-calling LLM round-trips) can
        # legitimately take longer than a few minutes. The previous 5-minute
        # timeout with the default unlimited retry policy meant a slow (but
        # otherwise healthy) triage run would get killed by Temporal,
        # silently restart from attempt 1, get killed again, and repeat
        # forever -- the incident just sat in INVESTIGATING indefinitely
        # with no visible error. Raise the timeout to give the agent chain
        # realistic headroom, and cap retries so a genuinely broken/hanging
        # triage fails visibly instead of looping silently.
        triage_result = await workflow.execute_activity(
            triage_incident_activity,
            incident_id,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        
        if triage_result.get("status") != "EXECUTED" or not triage_result.get("saved_plan"):
            workflow.logger.warning(f"Triage failed or no plan saved for {incident_id}")
            return {"status": "failed", "reason": "Triage failed"}

        # Note: triage_incident_activity currently updates the DB and creates the plan.
        # It's a bit hacky to rely on the DB to get the plan_id instead of returning it, 
        # but we can fetch it if needed or assume the frontend will send it in the signal.
        
        # 2. Block and wait for Human Approval Signal
        workflow.logger.info(f"Waiting for human approval for {incident_id}")
        await workflow.wait_condition(lambda: self.approval_decision is not None)
        
        # 3. Proceed based on approval
        if self.approval_decision == "approve":
            workflow.logger.info(f"Plan approved for {incident_id}. Executing.")
            await workflow.execute_activity(
                execute_plan_activity,
                {"incident_id": incident_id, "plan_id": self.plan_id},
                start_to_close_timeout=timedelta(minutes=5),
            )
            return {"status": "completed", "action": "executed"}
        else:
            workflow.logger.info(f"Plan rejected/cancelled for {incident_id}")
            return {"status": "completed", "action": "cancelled"}

    @workflow.signal(name="approve_plan")
    async def approve_plan(self, signal_data: Dict[str, Any]):
        """
        Signal received from the API when a human clicks 'Approve' or 'Reject'.
        signal_data should be like: {"decision": "approve", "plan_id": "PLN-123"}
        """
        self.approval_decision = signal_data.get("decision")
        self.plan_id = signal_data.get("plan_id")
