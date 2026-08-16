from typing import Dict, Any, List
from .base_agent import BaseAgent
from .agent_tools import _get_full_tools_schema, execute_tool_call, LOCALSTACK_LAB_ENABLED
import json

class RunbookAgent(BaseAgent):
    def __init__(self):
        # Structural policy enforcement (not just "hoping the LLM remembers"):
        # for any incident where the RCA finding indicates data was written
        # to a table before the failure, the FIRST recovery steps MUST be
        # staleness-check + conditional cleanup, and the rerun step MUST be
        # ordered strictly after them. This is stated as a hard constraint
        # here, and separately re-checked/enforced by the Grounding Critic
        # (see langgraph_investigator.py) which can reject a plan that
        # violates it.
        integrity_policy = """

MANDATORY DATA-INTEGRITY POLICY (LocalStack-lab incidents only):
If the RCA finding indicates the failing job writes to a database table (e.g. "order_events"),
your recovery steps MUST follow this exact ordering and MUST NOT skip any step:
  1. `check_table_staleness` for that table + run_id (read-only diagnostic; risk LOW).
  2. IF is_stale_or_partial is true: `cleanup_partial_write` with dry_run=true first (risk LOW),
     then a step describing the reviewed cleanup with dry_run=false (risk MEDIUM, requires approval).
     IF is_stale_or_partial is false: skip cleanup entirely and say so explicitly.
  3. Only THEN a step to rerun the job (risk MEDIUM).
  4. `verify_row_count_matches_expected` after the rerun (risk LOW) to confirm recovery worked
     before the incident can be marked resolved.
A plan that reruns a write-job WITHOUT a preceding staleness check (and cleanup if needed) is
UNSAFE and must not be produced — a naive rerun of a partially-written table will double-write
rows that already committed.""" if LOCALSTACK_LAB_ENABLED else ""

        super().__init__(
            agent_name="Runbook_Agent",
            model="nvidia/nemotron-3-super-120b-a12b",
            system_prompt=f"""You are the Runbook Agent.
Your job is to search the runbook library and propose actionable recovery steps based on the incident context.
Use the `get_runbook` tool to fetch standard operating procedures for the services identified in the alerts or RCA finding.

If `get_runbook`'s short database summary doesn't give enough procedural detail to write
specific, confident recovery steps (e.g. it only names a runbook, without concrete
diagnostic/verification steps), call `read_runbook_document` with a keyword matching the
failure type (e.g. 'schema_drift', 'partial_write', 'poison_pill', 'pipeline') to read the
FULL real runbook document text and base your steps on its actual diagnostic, remediation,
and verification sections.

Call `get_runbook` AT MOST ONCE, and `read_runbook_document` AT MOST ONCE. Do not retry with
different service names or keywords — if a tool returns a fallback/default/not-found result,
use whatever you have (or fall back to a generic manual-escalation step) and proceed directly
to your final JSON answer on your very next turn. Never loop.
{integrity_policy}

You MUST return ONLY valid JSON in this exact format:
{{
  "finding": "Summary of recommended runbooks",
  "steps": [
    {{"action": "Describe step", "tool": "tool_name", "risk": "LOW|MEDIUM|HIGH"}}
  ]
}}
If no specific runbook is found, still return at least one generic step (e.g. "Escalate to on-call engineer for manual review") rather than continuing to search.
"""
        )

    async def analyze(self, alerts: List[Dict], rca_finding: str = "") -> Dict[str, Any]:
        prompt = f"""
        Find applicable recovery steps for this incident by querying runbooks.
        
        ALERTS:
        {json.dumps(alerts, indent=2)}
        
        PRELIMINARY RCA (If available):
        {rca_finding}
        """
        
        response = await self.call_llm_with_tools(prompt, _get_full_tools_schema(), execute_tool_call)
        return response
