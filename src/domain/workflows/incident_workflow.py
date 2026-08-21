from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
from typing import Dict, Any, Optional

with workflow.unsafe.imports_passed_through():
    from src.domain.activities.triage_activity import triage_incident_activity
    from src.domain.activities.execution_activity import execute_plan_activity
    from src.domain.activities.lifecycle_activity import (
        transition_incident_state_activity,
        log_escalation_audit_event_activity,
    )

# Per docs/NemoGuard_Enterprise_Hardening_and_Productization_Build_Plan.md
# Priority 10 section 14.4 ("approval timeout / escalation timeout").
# Previously the workflow's `wait_condition` for the approval signal had NO
# timeout at all -- a plan nobody acted on would leave the workflow (and the
# incident) blocked indefinitely with zero automated escalation, silently
# defeating the entire point of having an SLA-aware incident response
# system. This is a workflow-level constant (not DB-configurable yet) since
# it governs Temporal's own timer, which must be a deterministic value known
# to the workflow itself.
APPROVAL_WAIT_TIMEOUT = timedelta(hours=4)


@workflow.defn
class IncidentLifecycleWorkflow:
    def __init__(self):
        self.approval_decision = None
        self.plan_id = None
        # Per build plan section 14.3 ("cancel ... should be workflow
        # signals ... avoid synchronous side channels that mutate lifecycle
        # state independently"). Previously there was NO way to cancel a
        # workflow that was blocked waiting for approval other than killing
        # the Temporal workflow out-of-band (which leaves no audit trail and
        # doesn't go through the incident state machine at all).
        self.cancel_requested = False
        self.cancel_reason = ""

    async def _transition(self, incident_id: str, to: str, reason: str) -> None:
        await workflow.execute_activity(
            transition_incident_state_activity,
            {"incident_id": incident_id, "to": to, "actor": "TEMPORAL_WORKFLOW", "reason": reason},
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

    @workflow.run
    async def run(self, incident_id: str, approval_wait_timeout_seconds: Optional[float] = None) -> dict:
        workflow.logger.info(f"Started IncidentLifecycleWorkflow for {incident_id}")
        # `approval_wait_timeout_seconds` defaults to the real
        # APPROVAL_WAIT_TIMEOUT constant in production (callers --
        # src/api/main.py's /triage and webhook-created-incident paths --
        # never pass this explicitly). Exposed as a plain float (rather
        # than a timedelta -- Temporal's default JSON payload converter
        # cannot serialize timedelta as a workflow *argument*, only as
        # activity/timer options) purely so tests can exercise the
        # timeout/escalation path with a tiny value instead of racing the
        # WorkflowEnvironment's time-skipping against a real multi-hour
        # magnitude timer, which is unreliable to test deterministically at
        # full production scale.
        effective_timeout = (
            timedelta(seconds=approval_wait_timeout_seconds)
            if approval_wait_timeout_seconds is not None
            else APPROVAL_WAIT_TIMEOUT
        )
        
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

        # 2. Explicitly enter AWAITING_APPROVAL. IncidentState.AWAITING_APPROVAL
        # has always existed in the state machine's valid-transition graph
        # (PLAN_READY -> AWAITING_APPROVAL -> {EXECUTING, INVESTIGATING,
        # CANCELLED, RESOLVED}), but the workflow itself never actually
        # performed this transition -- the incident silently stayed at
        # PLAN_READY for the entire approval wait, with no state (and no
        # audit event) reflecting that it was actually blocked awaiting a
        # human decision.
        await self._transition(incident_id, "AWAITING_APPROVAL", "Recovery plan ready; awaiting human approval.")

        # 3. Block and wait for a human decision, a cancel signal, OR the
        # approval timeout -- whichever comes first. Previously this was an
        # unconditional `wait_condition` with no timeout at all, meaning an
        # incident nobody acted on would block this workflow (and sit at
        # PLAN_READY) forever with zero automated escalation.
        workflow.logger.info(f"Waiting for human approval for {incident_id} (timeout={effective_timeout})")
        approval_received = await workflow.wait_condition(
            lambda: self.approval_decision is not None or self.cancel_requested,
            timeout=effective_timeout,
        )

        if self.cancel_requested:
            workflow.logger.info(f"Cancellation requested for {incident_id}: {self.cancel_reason}")
            await self._transition(
                incident_id, "CANCELLED", self.cancel_reason or "Cancelled via workflow signal."
            )
            return {"status": "completed", "action": "cancelled"}

        if not approval_received:
            # Timed out waiting for a decision -- escalate rather than
            # blocking forever (build plan section 14.4 "escalation
            # timeout"). Moves the incident back to INVESTIGATING (a legal
            # transition from AWAITING_APPROVAL) so it visibly falls out of
            # "awaiting approval" and re-enters the active work queue as
            # needing attention, and records an explicit escalation audit
            # event so operators can see exactly why/when this happened.
            workflow.logger.warning(f"Approval wait timed out for {incident_id}; escalating.")
            await workflow.execute_activity(
                log_escalation_audit_event_activity,
                {
                    "incident_id": incident_id,
                    "summary": f"No approval decision received within {effective_timeout}; escalated for human attention.",
                },
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            await self._transition(
                incident_id, "INVESTIGATING", "Approval wait timed out; escalated back to active investigation."
            )
            return {"status": "escalated", "reason": "approval_timeout"}

        # 4. Proceed based on approval
        if self.approval_decision == "approve":
            workflow.logger.info(f"Plan approved for {incident_id}. Executing.")
            await self._transition(incident_id, "EXECUTING", "Plan approved; beginning execution.")
            await workflow.execute_activity(
                execute_plan_activity,
                {"incident_id": incident_id, "plan_id": self.plan_id},
                start_to_close_timeout=timedelta(minutes=5),
            )
            return {"status": "completed", "action": "executed"}
        else:
            workflow.logger.info(f"Plan rejected/cancelled for {incident_id}")
            await self._transition(incident_id, "INVESTIGATING", "Plan rejected; returning to investigation.")
            return {"status": "completed", "action": "cancelled"}

    @workflow.signal(name="approve_plan")
    async def approve_plan(self, signal_data: Dict[str, Any]):
        """
        Signal received from the API when a human clicks 'Approve' or 'Reject'.
        signal_data should be like: {"decision": "approve", "plan_id": "PLN-123"}
        """
        self.approval_decision = signal_data.get("decision")
        self.plan_id = signal_data.get("plan_id")

    @workflow.signal(name="cancel_incident")
    async def cancel_incident(self, signal_data: Dict[str, Any]):
        """
        Per build plan section 14.3/14.4 ("cancel ... should be workflow
        signals"). Lets an operator explicitly cancel an incident that's
        still blocked awaiting approval, WITHOUT killing the Temporal
        workflow out-of-band -- this goes through the normal incident state
        machine (AWAITING_APPROVAL -> CANCELLED is a legal transition) and
        produces a real audit trail, unlike terminating the workflow
        directly.

        signal_data should be like: {"reason": "Duplicate of INC-XYZ"}
        """
        self.cancel_requested = True
        self.cancel_reason = signal_data.get("reason", "")
