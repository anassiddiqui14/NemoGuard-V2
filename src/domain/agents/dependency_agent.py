from typing import Dict, Any, List
from .base_agent import BaseAgent
from .agent_tools import AGENT_TOOLS_SCHEMA, execute_tool_call
import json

class DependencyAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="Dependency_Agent",
            model="nvidia/nemotron-3-super-120b-a12b",
            system_prompt="""You are the Dependency Agent.
Your job is to analyze the CMDB topology using the `get_cmdb_context` tool to identify downstream systems and jobs impacted by an incident root cause.

Call `get_cmdb_context` AT MOST ONCE. Do not retry with different service names — if the tool returns a fallback/no-match result, use whatever context it gave you (or an empty impacts list) and proceed directly to your final JSON answer on your very next turn. Never loop.

You MUST return ONLY valid JSON in this exact format:
{
  "finding": "Summary of dependencies affected",
  "impacts": [
    {"asset_id": "Affected Job or Table", "impact_type": "Downstream Job|Data Product", "status": "BLOCKED|AT_RISK", "reason": "Why it is affected"}
  ]
}
If no downstream dependencies can be confidently identified, return "impacts": [] rather than continuing to search.
"""
        )

    async def analyze(self, root_cause_finding: str) -> Dict[str, Any]:
        prompt = f"""
        The RCA agent has determined the following root cause:
        {root_cause_finding}
        
        Use the `get_cmdb_context` tool to explore the topology and determine all downstream impacts.
        Then, return the JSON containing the impacts.
        """
        
        response = await self.call_llm_with_tools(prompt, AGENT_TOOLS_SCHEMA, execute_tool_call)
        return response
