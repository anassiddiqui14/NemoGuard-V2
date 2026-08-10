from typing import Dict, Any, List
from .base_agent import BaseAgent
from .agent_tools import AGENT_TOOLS_SCHEMA, execute_tool_call
import json

class RunbookAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="Runbook_Agent",
            model="nvidia/nemotron-3-super-120b-a12b",
            system_prompt="""You are the Runbook Agent.
Your job is to search the runbook library and propose actionable recovery steps based on the incident context.
Use the `get_runbook` tool to fetch standard operating procedures for the services identified in the alerts or RCA finding.

Call `get_runbook` AT MOST ONCE. Do not retry with different service names — if the tool returns a fallback/default result, use it (or fall back to a generic manual-escalation step) and proceed directly to your final JSON answer on your very next turn. Never loop.

You MUST return ONLY valid JSON in this exact format:
{
  "finding": "Summary of recommended runbooks",
  "steps": [
    {"action": "Describe step", "tool": "tool_name", "risk": "LOW|MEDIUM|HIGH"}
  ]
}
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
        
        response = await self.call_llm_with_tools(prompt, AGENT_TOOLS_SCHEMA, execute_tool_call)
        return response
