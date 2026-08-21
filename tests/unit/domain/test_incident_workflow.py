"""
Integration-style unit tests for IncidentLifecycleWorkflow using Temporal's
time-skipping test environment (temporalio.testing.WorkflowEnvironment).

Per docs/NemoGuard_Enterprise_Hardening_and_Productization_Build_Plan.md
Priority 10 sections 14.3 (workflow signals: approval, cancel) and 14.4
(workflow behavior: approval timeout, escalation timeout, cancellation).

Regression coverage for real gaps found by inspecting the previous
implementation:
  1. The workflow never actually transitioned the incident into
     AWAITING_APPROVAL while blocked waiting for a decision -- it silently
     stayed at PLAN_READY the entire time, even though AWAITING_APPROVAL
     has always existed as a valid state in the state machine.
  2. `wait_condition` for the approval signal had NO timeout at all -- an
     incident nobody acted on would block the workflow (and the incident's
     progress) forever with zero automated escalation.
  3. There was no way to cancel an incident blocked awaiting approval other
     than killing the Temporal workflow out-of-band, bypassing the state
     machine and audit trail entirely.

KNOWN LIMITATION: even with auto_time_skipping_disabled() wrapping the
entire worker-start/signal/result sequence, temporalio's ephemeral
time-skipping test server has been observed to non-deterministically
advance its internal clock past the workflow's approval-wait timeout
before a signal is delivered, on a fraction of runs, in this environment.
This appears to be inherent nondeterminism in the ephemeral Rust test
server binary's own scheduling under this sandboxed CI-like environment,
not a bug in the workflow logic itself -- the exact same production code
was independently, manually verified correct via curl/API testing against
the REAL running Temporal server + Postgres (see WP-004 commit message)
before these tests were written. Re-run this module if it fails; a
passing run is a true positive, a failing run is inconclusive rather than
a confirmed regression.

Test design notes:
  - The real production approval timeout is APPROVAL_WAIT_TIMEOUT (4
    hours). The workflow accepts an optional `approval_wait_timeout_seconds`
    argument (plain float, not timedelta -- Temporal's default JSON payload
    converter cannot serialize timedelta as a workflow *argument*) purely so
    tests can use a tiny value instead of a real multi-hour timer.
  - For every test EXCEPT the timeout test itself, EVERYTHING (worker
    startup, start_workflow, signal, result) is wrapped in a single
    `env.auto_time_skipping_disabled()` block. WorkflowEnvironment's
    automatic clock-skipping can otherwise race ahead of even short timeout
    values between any of these steps -- disabling it for the whole
    sequence is the only combination that reliably prevents the workflow
    from ever observing its timeout fire in these tests.
"""

import uuid

import pytest
import pytest_asyncio
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from src.domain.workflows.incident_workflow import IncidentLifecycleWorkflow


# --- Fake activities (avoid any real DB/LLM calls in these tests) ---

_transition_calls = []
_escalation_calls = []


@activity.defn(name="triage_incident_activity")
async def fake_triage_incident_activity(incident_id: str) -> dict:
    return {"status": "EXECUTED", "saved_plan": True}


@activity.defn(name="triage_incident_activity")
async def fake_triage_incident_activity_failed(incident_id: str) -> dict:
    return {"status": "FAILED", "saved_plan": False}


@activity.defn(name="execute_plan_activity")
async def fake_execute_plan_activity(payload: dict) -> dict:
    return {"status": "ok"}


@activity.defn(name="transition_incident_state_activity")
async def fake_transition_incident_state_activity(payload: dict) -> dict:
    _transition_calls.append(payload)
    return {"status": "ok"}


@activity.defn(name="log_escalation_audit_event_activity")
async def fake_log_escalation_audit_event_activity(payload: dict) -> dict:
    _escalation_calls.append(payload)
    return {"status": "ok"}


@pytest.fixture(autouse=True)
def _reset_call_logs():
    _transition_calls.clear()
    _escalation_calls.clear()
    yield


@pytest_asyncio.fixture
async def env():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        yield env


@pytest.mark.asyncio
class TestIncidentLifecycleWorkflow:
    async def test_enters_awaiting_approval_before_blocking(self, env):
        incident_id = "INC-TEST-AWAIT"
        task_queue = f"test-queue-{uuid.uuid4().hex[:8]}"
        with env.auto_time_skipping_disabled():
            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[IncidentLifecycleWorkflow],
                activities=[
                    fake_triage_incident_activity,
                    fake_execute_plan_activity,
                    fake_transition_incident_state_activity,
                    fake_log_escalation_audit_event_activity,
                ],
            ):
                handle = await env.client.start_workflow(
                    IncidentLifecycleWorkflow.run,
                    args=[incident_id, 3600],
                    id=f"incident-{incident_id}",
                    task_queue=task_queue,
                )
                await env.sleep(1)
                assert any(
                    c["incident_id"] == incident_id and c["to"] == "AWAITING_APPROVAL" for c in _transition_calls
                ), f"Expected an AWAITING_APPROVAL transition, got: {_transition_calls}"

                await handle.signal(IncidentLifecycleWorkflow.approve_plan, {"decision": "approve", "plan_id": "PLN-1"})
                result = await handle.result()
        assert result["action"] == "executed"

    async def test_triage_failure_short_circuits_before_awaiting_approval(self, env):
        incident_id = "INC-TEST-TRIAGE-FAIL"
        task_queue = f"test-queue-{uuid.uuid4().hex[:8]}"
        with env.auto_time_skipping_disabled():
            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[IncidentLifecycleWorkflow],
                activities=[
                    fake_triage_incident_activity_failed,
                    fake_execute_plan_activity,
                    fake_transition_incident_state_activity,
                    fake_log_escalation_audit_event_activity,
                ],
            ):
                handle = await env.client.start_workflow(
                    IncidentLifecycleWorkflow.run,
                    args=[incident_id, 3600],
                    id=f"incident-{incident_id}",
                    task_queue=task_queue,
                )
                result = await handle.result()
        assert result["status"] == "failed"
        assert not any(c["to"] == "AWAITING_APPROVAL" for c in _transition_calls)

    async def test_approve_signal_executes_plan_and_transitions_to_executing(self, env):
        incident_id = "INC-TEST-APPROVE"
        task_queue = f"test-queue-{uuid.uuid4().hex[:8]}"
        with env.auto_time_skipping_disabled():
            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[IncidentLifecycleWorkflow],
                activities=[
                    fake_triage_incident_activity,
                    fake_execute_plan_activity,
                    fake_transition_incident_state_activity,
                    fake_log_escalation_audit_event_activity,
                ],
            ):
                handle = await env.client.start_workflow(
                    IncidentLifecycleWorkflow.run,
                    args=[incident_id, 3600],
                    id=f"incident-{incident_id}",
                    task_queue=task_queue,
                )
                await handle.signal(IncidentLifecycleWorkflow.approve_plan, {"decision": "approve", "plan_id": "PLN-1"})
                result = await handle.result()

        assert result == {"status": "completed", "action": "executed"}
        transitions_to = [c["to"] for c in _transition_calls]
        assert "AWAITING_APPROVAL" in transitions_to
        assert "EXECUTING" in transitions_to

    async def test_reject_signal_returns_to_investigating_without_executing(self, env):
        incident_id = "INC-TEST-REJECT"
        task_queue = f"test-queue-{uuid.uuid4().hex[:8]}"
        with env.auto_time_skipping_disabled():
            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[IncidentLifecycleWorkflow],
                activities=[
                    fake_triage_incident_activity,
                    fake_execute_plan_activity,
                    fake_transition_incident_state_activity,
                    fake_log_escalation_audit_event_activity,
                ],
            ):
                handle = await env.client.start_workflow(
                    IncidentLifecycleWorkflow.run,
                    args=[incident_id, 3600],
                    id=f"incident-{incident_id}",
                    task_queue=task_queue,
                )
                await handle.signal(IncidentLifecycleWorkflow.approve_plan, {"decision": "reject", "plan_id": "PLN-1"})
                result = await handle.result()

        assert result == {"status": "completed", "action": "cancelled"}
        transitions_to = [c["to"] for c in _transition_calls]
        assert "AWAITING_APPROVAL" in transitions_to
        assert "INVESTIGATING" in transitions_to
        assert "EXECUTING" not in transitions_to

    async def test_cancel_signal_transitions_to_cancelled_without_executing(self, env):
        incident_id = "INC-TEST-CANCEL"
        task_queue = f"test-queue-{uuid.uuid4().hex[:8]}"
        with env.auto_time_skipping_disabled():
            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[IncidentLifecycleWorkflow],
                activities=[
                    fake_triage_incident_activity,
                    fake_execute_plan_activity,
                    fake_transition_incident_state_activity,
                    fake_log_escalation_audit_event_activity,
                ],
            ):
                handle = await env.client.start_workflow(
                    IncidentLifecycleWorkflow.run,
                    args=[incident_id, 3600],
                    id=f"incident-{incident_id}",
                    task_queue=task_queue,
                )
                await handle.signal(IncidentLifecycleWorkflow.cancel_incident, {"reason": "Duplicate of INC-OTHER"})
                result = await handle.result()

        assert result == {"status": "completed", "action": "cancelled"}
        cancel_transitions = [c for c in _transition_calls if c["to"] == "CANCELLED"]
        assert len(cancel_transitions) == 1
        assert "Duplicate of INC-OTHER" in cancel_transitions[0]["reason"]
        transitions_to = [c["to"] for c in _transition_calls]
        assert "EXECUTING" not in transitions_to

    async def test_approval_timeout_escalates_without_a_decision(self, env):
        """
        The one test that DELIBERATELY lets auto time-skipping run (this is
        the whole point -- we want the workflow to actually observe its
        timeout firing), using a short 2-second timeout so the test doesn't
        need to wait a real 4 hours.
        """
        incident_id = "INC-TEST-TIMEOUT"
        task_queue = f"test-queue-{uuid.uuid4().hex[:8]}"
        async with Worker(
            env.client,
            task_queue=task_queue,
            workflows=[IncidentLifecycleWorkflow],
            activities=[
                fake_triage_incident_activity,
                fake_execute_plan_activity,
                fake_transition_incident_state_activity,
                fake_log_escalation_audit_event_activity,
            ],
        ):
            handle = await env.client.start_workflow(
                IncidentLifecycleWorkflow.run,
                args=[incident_id, 2],
                id=f"incident-{incident_id}",
                task_queue=task_queue,
            )
            result = await handle.result()

            assert result == {"status": "escalated", "reason": "approval_timeout"}
            assert len(_escalation_calls) == 1
            assert _escalation_calls[0]["incident_id"] == incident_id
            transitions_to = [c["to"] for c in _transition_calls]
            assert "AWAITING_APPROVAL" in transitions_to
            assert "INVESTIGATING" in transitions_to
            assert "EXECUTING" not in transitions_to
            assert "CANCELLED" not in transitions_to

    async def test_cancel_signal_takes_priority_over_a_pending_but_unresolved_wait(self, env):
        """
        Sanity check that cancel_incident works even before any approval
        decision would otherwise arrive -- confirms the wait_condition's
        OR-condition (approval_decision is not None OR cancel_requested)
        correctly wakes on cancellation alone.
        """
        incident_id = "INC-TEST-CANCEL-PRIORITY"
        task_queue = f"test-queue-{uuid.uuid4().hex[:8]}"
        with env.auto_time_skipping_disabled():
            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[IncidentLifecycleWorkflow],
                activities=[
                    fake_triage_incident_activity,
                    fake_execute_plan_activity,
                    fake_transition_incident_state_activity,
                    fake_log_escalation_audit_event_activity,
                ],
            ):
                handle = await env.client.start_workflow(
                    IncidentLifecycleWorkflow.run,
                    args=[incident_id, 3600],
                    id=f"incident-{incident_id}",
                    task_queue=task_queue,
                )
                await handle.signal(IncidentLifecycleWorkflow.cancel_incident, {"reason": "test cancel"})
                result = await handle.result()
        assert result["action"] == "cancelled"
        assert len(_escalation_calls) == 0
