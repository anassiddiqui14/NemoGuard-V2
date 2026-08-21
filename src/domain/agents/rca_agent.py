from typing import Dict, Any, List
from .base_agent import BaseAgent
from .agent_tools import _get_full_tools_schema, execute_tool_call, LOCALSTACK_LAB_ENABLED
import json

class RCAAgent(BaseAgent):
    def __init__(self):
        # When the LocalStack lab is enabled, the RCA agent also has access
        # to real CloudWatch Logs / S3 / Lambda-metrics tools and is
        # instructed to use them to build a complete picture (not just
        # NemoGuard's own synthetic log_event table) before concluding.
        lab_extra = """

You ALSO have access to real infrastructure tools when investigating a LocalStack-lab-sourced
incident (tags containing "env:localstack-lab", or a run_id starting with "RUN-LOCALSTACK-"):
  - `query_cloudwatch_logs`: the REAL, complete application log stream for the failing
    Lambda (log group name is "/aws/lambda/<function-name>", e.g.
    "/aws/lambda/nemoguard-ingest-job" or "/aws/lambda/nemoguard-order-events-job").
    Use this to see the actual stack trace/error, not just what got echoed into log_event.
  - `list_s3_objects` / `read_s3_object`: inspect the actual input file (bucket
    "nemoguard-lab-data") that caused the failure, to confirm the exact malformed/missing
    data rather than inferring it purely from a stack trace.
  - `describe_lambda_invocation`: real Invocations/Errors/Duration metrics for the function,
    to determine whether this is a one-off failure or a sustained error spike.
  - If the failing job WRITES to a database table (e.g. "order_events"), you MUST also call
    `check_table_staleness` for that table+run_id as part of your investigation, and include
    its result in your evidence -- a partial/stale write changes the correct recovery plan
    (cleanup is required before any rerun) and downstream agents rely on you having checked
    this.
  - `get_sqs_queue_attributes` / `peek_sqs_messages`: for queue-based incidents, check for a
    backed-up consumer or inspect a suspected poison-pill message.
  - `list_sns_subscriptions`: confirm alert/notification routing is actually wired as expected.
  - `describe_rds_instance_status`: check if the incident's database itself is degraded
    (storage-full, failing over) as the underlying root cause.
  - `describe_ecs_task_status`: for containerized (non-Lambda) services, check running vs.
    desired task count and recent stopped-task reasons.
  - `describe_step_function_execution`: for state-machine-orchestrated jobs, see which state
    failed and why.
  - `check_iam_role_permissions`: diagnose AccessDenied-type failures by simulating (read-only)
    whether a role actually has the permission it needs.
  - `get_secret_metadata`: check if a credential rotation happened recently as a possible cause
    of a sudden auth failure (this NEVER exposes the secret value itself).
  - `describe_ec2_instance_status`: for self-hosted workers on EC2, check system/instance health.
  - `list_recent_changes`: ALWAYS call this for the primary failing resource. A recent
    deployment/config change correlated in time with the failure is one of the strongest
    causal signals available -- check it before concluding root cause, not after.
Use whichever of these are relevant; you do not need to call all of them for every incident.""" if LOCALSTACK_LAB_ENABLED else ""

        hypothesis_ledger_instructions = """

HYPOTHESIS LEDGER (structured, evidence-tracked reasoning):
Do NOT collapse your reasoning into a single "finding" string. Instead, generate MULTIPLE
competing hypotheses (at least 2, even if one is clearly weaker), rank them by confidence, and
for EACH hypothesis explicitly list which evidence supports it and which evidence (if any)
contradicts it. This lets a human reviewer see your reasoning process, not just your
conclusion, and lets the system track when new evidence should change your ranking."""

        super().__init__(
            agent_name="RCA_Agent",
            # Root-cause diagnosis is the single most consequential decision in the pipeline
            # (everything downstream — impact, runbook selection, the recovery plan — depends
            # on getting this right), so we route it to the larger/stronger reasoning model.
            model="nvidia/nemotron-3-ultra-550b-a55b",
            system_prompt=f"""You are the Root Cause Analysis (RCA) Agent. 
Your job is to investigate an incident by querying logs.
Use the `query_logs` tool to fetch logs for the incident ONCE. Do NOT loop or call the tool multiple times unnecessarily.
{lab_extra}
{hypothesis_ledger_instructions}

You MUST return ONLY valid JSON in this exact format as your final response once you have determined the root cause:
{{
  "finding": "Detailed explanation of the PRIMARY (highest-confidence) root cause -- must match hypotheses[0].statement",
  "cause_type": "SCHEMA_REGRESSION|DATA_QUALITY|RESOURCE_EXHAUSTION|PARTIAL_WRITE|OTHER",
  "confidence": 0.95,
  "evidence": [
    {{"type": "Log|Alert|CloudWatchLog|S3Object|TableStaleness|ChangeEvent", "title": "Brief title", "excerpt": "Relevant text"}}
  ],
  "hypotheses": [
    {{
      "statement": "The primary, most likely explanation",
      "cause_type": "SCHEMA_REGRESSION|DATA_QUALITY|RESOURCE_EXHAUSTION|PARTIAL_WRITE|OTHER",
      "confidence": 0.95,
      "supporting_evidence_titles": ["Title of evidence item that supports this"],
      "contradicting_evidence_titles": []
    }},
    {{
      "statement": "A plausible but less likely alternative explanation you considered and ruled down (not out)",
      "cause_type": "...",
      "confidence": 0.25,
      "supporting_evidence_titles": [],
      "contradicting_evidence_titles": ["Title of evidence item that argues against this"]
    }}
  ],
  "data_integrity": {{
    "checked": true|false,
    "is_stale_or_partial": true|false,
    "details": "Result of check_table_staleness if a write-job was involved, else empty string"
  }}
}}
"""
        )

    async def analyze(self, incident_id: str) -> Dict[str, Any]:
        prompt = f"""
        Analyze the root cause for incident {incident_id}. 
        Use the `query_logs` tool to gather evidence before returning your JSON conclusion.
        If this looks like a LocalStack-lab-sourced incident and the failing job writes to a
        database table, also use the real observability + data-integrity tools described in
        your instructions (query_cloudwatch_logs, list_s3_objects/read_s3_object,
        check_table_staleness) to build a complete, verified picture.
        """
        
        # LocalStack-lab investigations legitimately involve several distinct
        # real-infrastructure tool calls (query_cloudwatch_logs, list_s3_objects,
        # read_s3_object, describe_lambda_invocation, check_table_staleness,
        # list_recent_changes, ...) before a final answer -- the previous
        # default of 5 iterations was too tight and caused this agent to fail
        # with "exceeded maximum allowed tool iterations" on real lab incidents,
        # forcing the Grounding Critic to fall back to a substitute plan
        # instead of a genuine RCA finding. Give RCA a larger budget than the
        # BaseAgent default since it is the most tool-intensive agent and the
        # most consequential to get right.
        max_iters = 12 if LOCALSTACK_LAB_ENABLED else 5
        response = await self.call_llm_with_tools(prompt, _get_full_tools_schema(), execute_tool_call, max_iterations=max_iters)
        return response
