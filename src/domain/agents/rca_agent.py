from typing import Dict, Any, List
from .base_agent import BaseAgent
from .agent_tools import AGENT_TOOLS_SCHEMA, execute_tool_call
import json

class RCAAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="RCA_Agent",
            # Root-cause diagnosis is the single most consequential decision in the pipeline
            # (everything downstream — impact, runbook selection, the recovery plan — depends
            # on getting this right), so we route it to the larger/stronger reasoning model.
            model="nvidia/nemotron-3-ultra-550b-a55b",
            system_prompt="""You are the Root Cause Analysis (RCA) Agent. 
Your job is to investigate an incident by querying logs.
Use the `query_logs` tool to fetch logs for the incident ONCE. Do NOT loop or call the tool multiple times.

You MUST return ONLY valid JSON in this exact format as your final response once you have determined the root cause:
{
  "finding": "Detailed explanation of the root cause",
  "cause_type": "SCHEMA_REGRESSION|DATA_QUALITY|RESOURCE_EXHAUSTION|OTHER",
  "confidence": 0.95,
  "evidence": [
    {"type": "Log|Alert", "title": "Brief title", "excerpt": "Relevant text"}
  ]
}
"""
        )

    async def analyze(self, incident_id: str) -> Dict[str, Any]:
        prompt = f"""
        Analyze the root cause for incident {incident_id}. 
        Use the `query_logs` tool to gather evidence before returning your JSON conclusion.
        """
        
        response = await self.call_llm_with_tools(prompt, AGENT_TOOLS_SCHEMA, execute_tool_call)
        return response
