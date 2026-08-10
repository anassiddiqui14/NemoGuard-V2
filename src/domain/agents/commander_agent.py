from typing import Dict, Any, List
from .base_agent import BaseAgent
import json

class CommanderAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="Commander_Agent",
            model="nvidia/nemotron-3-ultra-550b-a55b",
            system_prompt="""You are the Incident Commander.
Your job is to synthesize findings from specialized sub-agents (RCA, Dependency, Runbook) into a final unified recovery plan.
You MUST return ONLY valid JSON in this exact format expected by the downstream API:
{
  "evidence": [
    {"type": "Log|Alert", "source": "System Name", "title": "Brief title", "excerpt": "Relevant extracted text"}
  ],
  "hypotheses": [
    {"statement": "Explanation of the root cause", "cause_type": "SCHEMA_REGRESSION|DATA_QUALITY|RESOURCE_EXHAUSTION|OTHER", "confidence": 0.95}
  ],
  "impacts": [
    {"asset_id": "Affected Job or Table", "impact_type": "Downstream Job|Data Product", "status": "BLOCKED|AT_RISK", "reason": "Why it is affected", "score": 0.8}
  ],
  "action_plan": {
    "rationale": "Why we are doing this",
    "expected_outcome": "What this will fix",
    "risk": "LOW|MEDIUM|HIGH",
    "steps": [
      {"action": "Describe step", "tool": "tool_name", "risk": "LOW|MEDIUM|HIGH"}
    ]
  }
}
"""
        )

    async def synthesize(self, alerts: List[Dict], rca_result: Dict, dep_result: Dict, rb_result: Dict) -> Dict[str, Any]:
        prompt = f"""
        Synthesize the final incident recovery plan using the data collected by the sub-agents.
        
        ALERTS:
        {json.dumps(alerts, indent=2)}
        
        RCA AGENT FINDINGS:
        {json.dumps(rca_result, indent=2)}
        
        DEPENDENCY AGENT FINDINGS:
        {json.dumps(dep_result, indent=2)}
        
        RUNBOOK AGENT FINDINGS:
        {json.dumps(rb_result, indent=2)}
        """
        
        response = await self.call_llm_json(prompt)
        return response
