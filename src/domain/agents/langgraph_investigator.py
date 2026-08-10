from typing import TypedDict, Dict, Any, List
import asyncio
from langgraph.graph import StateGraph, END, START

from src.domain.agents.rca_agent import RCAAgent
from src.domain.agents.dependency_agent import DependencyAgent
from src.domain.agents.runbook_agent import RunbookAgent
from src.domain.agents.base_agent import BaseAgent

class InvestigationState(TypedDict):
    incident_id: str
    alerts: List[Dict[str, Any]]
    
    rca_result: Dict[str, Any]
    impact_result: Dict[str, Any]
    runbook_result: Dict[str, Any]
    
    critic_passed: bool
    critic_feedback: str
    final_plan: Dict[str, Any]

class GroundingCritic(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="Grounding_Critic",
            # Final safety/grounding gate before a plan reaches a human approver — route to the
            # stronger model since this is the last automated check standing between the AI's
            # output and a real recovery action.
            model="nvidia/nemotron-3-ultra-550b-a55b",
            system_prompt="""You are the Grounding Critic.
You evaluate the outputs of RCA, Business Impact, and Runbook retrieval.
You must ensure that all factual claims have evidence citations.
Return ONLY valid JSON in the following format:
{
  "passed": true|false,
  "feedback": "Your critique here",
  "final_plan": {
    "rationale": "Combined summary of RCA, impact and runbook",
    "expected_outcome": "System restored",
    "risk": "MEDIUM",
    "steps": [
       {"action": "Step action", "tool": "manual", "risk": "LOW"}
    ]
  }
}"""
        )
        
    async def analyze(self, rca: Dict, impact: Dict, runbook: Dict) -> Dict:
        prompt = f"""
        RCA Result: {rca}
        IMPACT Result: {impact}
        RUNBOOK Result: {runbook}
        
        Critique the findings for evidence grounding and combine them into a final recovery plan.
        """
        import json
        return await self.call_llm_json(prompt)

class LangGraphInvestigator:
    def __init__(self):
        self.rca_agent = RCAAgent()
        self.dep_agent = DependencyAgent()
        self.runbook_agent = RunbookAgent()
        self.critic = GroundingCritic()
        self.graph = self._build_graph()
        
    def _build_graph(self):
        workflow = StateGraph(InvestigationState)
        
        # Define nodes
        async def run_rca(state: InvestigationState):
            res = await self.rca_agent.analyze(state["incident_id"])
            return {"rca_result": res}
            
        async def run_impact(state: InvestigationState):
            # Impact analysis is only meaningful once we actually know the root cause — running
            # this in parallel with RCA (as before) meant the Impact Agent was guessing blindly
            # off a placeholder string like "Investigating incident X" instead of the real
            # finding. We now run RCA first and feed its concrete finding into the Impact Agent,
            # so impact/blast-radius reasoning is grounded in actual evidence rather than generic
            # incident metadata.
            rca_finding = state.get("rca_result", {}).get("finding") or f"Investigating incident {state['incident_id']}"
            res = await self.dep_agent.analyze(rca_finding)
            return {"impact_result": res}
            
        async def run_runbook(state: InvestigationState):
            # Likewise, runbook selection should be informed by the confirmed root cause (not
            # just the raw alert list) so the retrieved procedure actually matches the failure
            # mode instead of a keyword-only match against alert text.
            rca_finding = state.get("rca_result", {}).get("finding", "")
            res = await self.runbook_agent.analyze(state.get("alerts", []), rca_finding=rca_finding)
            return {"runbook_result": res}
            
        async def run_critic(state: InvestigationState):
            res = await self.critic.analyze(
                state.get("rca_result", {}), 
                state.get("impact_result", {}), 
                state.get("runbook_result", {})
            )
            return {
                "critic_passed": res.get("passed", False),
                "critic_feedback": res.get("feedback", ""),
                "final_plan": res.get("final_plan", {})
            }
            
        # Add nodes
        workflow.add_node("rca", run_rca)
        workflow.add_node("impact", run_impact)
        workflow.add_node("runbook", run_runbook)
        workflow.add_node("critic", run_critic)
        
        # Edges: RCA must complete first since impact/runbook grounding depends on its finding
        # (see comments on run_impact/run_runbook above). Impact and runbook then run in
        # parallel off the same confirmed root cause before both feed into the critic.
        workflow.add_edge(START, "rca")
        workflow.add_edge("rca", "impact")
        workflow.add_edge("rca", "runbook")
        
        workflow.add_edge("impact", "critic")
        workflow.add_edge("runbook", "critic")
        
        workflow.add_edge("critic", END)
        
        return workflow.compile()
        
    async def investigate(self, incident_id: str, alerts: List[Dict] = None, audit_callback=None):
        if alerts is None:
            alerts = []
        state = {
            "incident_id": incident_id,
            "alerts": alerts,
            "rca_result": {},
            "impact_result": {},
            "runbook_result": {},
            "critic_passed": False,
            "critic_feedback": "",
            "final_plan": {}
        }
        
        final_state = dict(state)
        async for event in self.graph.astream(state):
            for node_name, updates in event.items():
                # Merge updates into our running state
                final_state.update(updates)
                
                # Fire live audit logs
                if audit_callback:
                    if node_name == "rca":
                        audit_callback(incident_id, "RCA Agent", "HYPOTHESIS_CREATED", "RCA Agent isolated root cause based on execution logs.")
                    elif node_name == "impact":
                        audit_callback(incident_id, "Impact Agent", "IMPACT_CALCULATED", "Impact Agent identified downstream dependencies from CMDB.")
                    elif node_name == "runbook":
                        audit_callback(incident_id, "Runbook Agent", "RUNBOOK_RETRIEVED", "Runbook Agent matched incident to standard recovery steps.")
                    elif node_name == "critic":
                        if updates.get("critic_passed"):
                            audit_callback(incident_id, "Safety Agent", "SAFETY_VALIDATION_PASSED", "Safety Agent validated plan parameters and verified blast radius is contained.")
                        else:
                            audit_callback(incident_id, "Safety Agent", "SAFETY_VALIDATION_FAILED", f"Safety Agent rejected plan: {updates.get('critic_feedback')}")

        return final_state
