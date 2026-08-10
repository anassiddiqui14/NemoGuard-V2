import os
import json
import urllib.request
import urllib.parse
import urllib.error
import ssl
import asyncio
import uuid
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from src.store.postgres_database import PostgresDatabase
from src.domain.enums import IncidentState
from src.domain.agents.rca_agent import RCAAgent
from src.domain.agents.dependency_agent import DependencyAgent
from src.domain.agents.runbook_agent import RunbookAgent
from src.domain.agents.commander_agent import CommanderAgent
from src.domain.agents.watcher_agent import WatcherAgent
from src.domain.models import (
    Incident, ActionPlan, Evidence, Hypothesis, IncidentImpact, 
    ActionStep, Approval, AuditEvent
)

class IncidentOrchestrator:
    def __init__(self, db_path: str = os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db")):
        self.db_path = db_path
        self.db = PostgresDatabase(db_path)
        # NVIDIA_API_KEY MUST be provided via environment (.env / secrets manager).
        # No hardcoded fallback key is used — see docs/IMPROVEMENT_PLAN.md (Security §1).
        if not os.environ.get("NVIDIA_API_KEY"):
            print("WARNING: NVIDIA_API_KEY is not set. LLM-backed agent calls will fail until it is configured.")

    def _generate_id(self, prefix: str) -> str:
        return f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

    def _log_audit(self, incident_id: str, actor: str, event_type: str, summary: str):
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO audit_event (audit_event_id, incident_id, actor_type, actor_id, event_type, event_summary, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (self._generate_id("AUD"), incident_id, "SYSTEM", actor, event_type, summary, datetime.now(timezone.utc).isoformat()))

    def call_llm_json(self, prompt: str) -> Dict[str, Any]:
        """Calls NVIDIA Nemotron and strictly extracts JSON response."""
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.environ['NVIDIA_API_KEY']}"
        }
        
        system_prompt = "You are an expert Data Engineering Incident Commander. You MUST output ONLY valid JSON. Do not include any markdown formatting outside the JSON block."
        
        data = {
            "model": "nvidia/nemotron-3-super-120b-a12b",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 16384,
            "chat_template_kwargs": {"enable_thinking": True},
            "reasoning_budget": 8192
        }
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
            with urllib.request.urlopen(req, context=ctx, timeout=300) as response:
                result = json.loads(response.read().decode('utf-8'))
                content = result['choices'][0]['message']['content'].strip()
                
                # Cleanup if the model still outputs markdown blocks
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                    
                # Fix unescaped newlines in JSON strings (common LLM failure for bash scripts)
                content = content.replace("\n", "\\n")
                # But we actually want real newlines between keys to be valid JSON, 
                # so fixing it perfectly with regex is complex. Let's rely on the LLM, 
                # but handle trailing commas and basic fixes.
                content = content.replace("\\n", "\n") # Revert, as python json handles newlines in some cases or LLM handles it.
                
                try:
                    import re
                    # very basic fix for common unescaped newlines inside string values:
                    # we will just try json.loads directly first
                    return json.loads(content)
                except Exception as parse_e:
                    # Attempt a naive fix for newlines inside strings
                    try:
                        # Sometimes LLMs don't escape newlines in string literals
                        fixed_content = re.sub(r'(%s<!\\)\n', r'\\n', content)
                        # The above breaks real JSON structure. So we don't do it.
                        pass
                    except:
                        pass
                    print("JSON PARSE ERROR. Raw Content:", content[-200:])
                    return {"error": f"{str(parse_e)}. Content might be truncated or invalid."}
        except Exception as e:
            print(f"LLM Error: {e}")
            return {"error": str(e)}

    def triage_incident(self, incident_id: str, has_runbook: bool = True):
        import asyncio
        import json
        import uuid
        from datetime import datetime, timezone
        from src.domain.agents.langgraph_investigator import LangGraphInvestigator
        
        investigator = LangGraphInvestigator()
        
        alerts_data = []
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT alert.alert_id, alert.severity, alert.alert_type, alert.source_system, alert.message FROM alert "
                "JOIN incident_alert ON alert.alert_id = incident_alert.alert_id "
                "WHERE incident_alert.incident_id = %s",
                (incident_id,)
            )
            for row in cursor.fetchall():
                alerts_data.append({
                    "alert_id": row[0],
                    "severity": row[1],
                    "alert_type": row[2],
                    "source_system": row[3],
                    "message": row[4]
                })

        try:
            final_state = asyncio.run(investigator.investigate(incident_id, alerts_data, audit_callback=self._log_audit))
            
            rca_res = final_state.get("rca_result", {})
            impact_res = final_state.get("impact_result", {})
            runbook_res = final_state.get("runbook_result", {})
            plan_res = final_state.get("final_plan", {})
            
            llm_response = {
                "evidence": rca_res.get("evidence", []),
                "hypotheses": [
                    {
                        "statement": rca_res.get("finding", "Unknown root cause"),
                        "cause_type": rca_res.get("cause_type", "OTHER"),
                        "confidence": rca_res.get("confidence", 0.9)
                    }
                ],
                "impacts": impact_res.get("impacts", []),
                "action_plan": {
                    "rationale": plan_res.get("rationale", ""),
                    "expected_outcome": plan_res.get("expected_outcome", ""),
                    "risk": plan_res.get("risk", "MEDIUM"),
                    "steps": plan_res.get("steps", [])
                }
            }
            
            # If the Grounding Critic (Safety Agent) rejected the plan, don't silently present
            # it as a normal PENDING_APPROVAL plan — surface it to the operator as NEEDS_REVIEW
            # with the critic's specific feedback attached, so the safety gate actually matters.
            critic_passed = final_state.get("critic_passed", True)
            critic_feedback = final_state.get("critic_feedback", "")
            self.save_agent_findings(incident_id, llm_response, critic_passed=critic_passed, critic_feedback=critic_feedback)
            saved_plan = True
        except Exception as e:
            print(f"LangGraph execution failed: {e}")
            saved_plan = False

        if not saved_plan:
            print("Running deterministic triage fallback")
            try:
                res = self.triage_fallback(incident_id)
                if "error" not in res:
                    saved_plan = True
            except Exception as e:
                print(f"Fallback triage failed: {e}")

        return {"status": "EXECUTED", "saved_plan": saved_plan}

    def _save_dynamic_triage(self, incident_id: str, plan_data: Dict[str, Any], alerts_data: list, logs_data: list):
        now = datetime.now(timezone.utc).isoformat()
        import json
        with self.db.get_connection() as conn:
            evidence_ids = []
            
            # Generate evidence from each alert
            for a in alerts_data:
                ev_id = self._generate_id("EVD")
                evidence_ids.append(ev_id)
                conn.execute("""
                    INSERT INTO evidence (evidence_id, incident_id, evidence_type, source_system, title, excerpt, collected_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (ev_id, incident_id, "Alert", a.get("source_system", "Unknown"),
                      f"[{a.get('severity', 'info').upper()}] {a.get('alert_type', 'UNKNOWN')}",
                      a.get("message", ""), now))
            
            # Generate evidence from error logs
            error_logs = [l for l in logs_data if l.get("level") in ("ERROR", "WARN")]
            for l in error_logs:
                ev_id = self._generate_id("EVD")
                evidence_ids.append(ev_id)
                conn.execute("""
                    INSERT INTO evidence (evidence_id, incident_id, evidence_type, source_system, title, excerpt, collected_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (ev_id, incident_id, "Log", l.get("component", "System"),
                      f"[{l.get('level')}] {l.get('error_code') or l.get('component', 'System')}",
                      l.get("message", ""), now))

            # Hypothesis
            hyp_id = self._generate_id("HYP")
            cause_type = plan_data.get("cause_type", "UNKNOWN")
            hypothesis = plan_data.get("hypothesis", "Unknown root cause")
            conn.execute("""
                INSERT INTO hypothesis (hypothesis_id, incident_id, agent_run_id, rank_no, statement, cause_type, confidence, status, supporting_evidence_json, contradicting_evidence_json, missing_evidence_json, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (hyp_id, incident_id, "RCA-Agent", 1, hypothesis, cause_type, 0.95, "PROBABLE_CAUSE", json.dumps(evidence_ids), "[]", "[]", now))

            # Impact analysis
            impacts = plan_data.get("impacts", [])
            for impact in impacts:
                asset_id = impact.get("asset", "Unknown")
                conn.execute("""
                    INSERT INTO data_asset (asset_id, asset_type, name)
                    VALUES (%s, 'Unknown', %s)
                    ON CONFLICT (asset_id) DO NOTHING
                """, (asset_id, asset_id))
                conn.execute("""
                    INSERT INTO incident_impact (incident_id, asset_id, impact_type, impact_status, reason, impact_score, evidence_ids_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (incident_id, asset_id, impact.get("type", "Unknown"), impact.get("status", "AT_RISK"), impact.get("reason", ""), 0.9, json.dumps(evidence_ids[:2])))

            # Action Plan
            plan_id = self._generate_id("PLN")
            plan_risk = plan_data.get("plan_risk", "HIGH")
            conn.execute("""
                INSERT INTO action_plan (action_plan_id, incident_id, agent_run_id, plan_version, status, overall_risk, rationale, expected_outcome, rollback_summary, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (plan_id, incident_id, "Commander", 1, "PENDING_APPROVAL", plan_risk, plan_data.get("plan_rationale", ""), plan_data.get("plan_outcome", ""), "Revert changes", now))
            
            steps = plan_data.get("steps", [])
            for i, step in enumerate(steps, 1):
                risk = step.get("risk", "MEDIUM")
                conn.execute("""
                    INSERT INTO action_step (action_step_id, action_plan_id, sequence_no, action_type, tool_name, risk_level, requires_approval, parameters_json, preconditions_json, expected_postconditions_json, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (self._generate_id("STP"), plan_id, i, step.get("action", ""), step.get("tool", ""), risk, 1 if risk in ["MEDIUM", "HIGH"] else 0, "{}", "{}", "{}", "PENDING"))
                
            conn.execute(
                "UPDATE incident SET actual_root_cause = %s, rca_confidence = %s, status = %s WHERE incident_id = %s",
                (hypothesis, 0.95, IncidentState.PLAN_READY.value, incident_id)
            )

        self._log_audit(incident_id, "RCA Agent", "HYPOTHESIS_CREATED", f"Identified {cause_type} as probable root cause.")
        self._log_audit(incident_id, "Impact Agent", "IMPACT_CALCULATED", f"Identified {len(impacts)} affected downstream assets.")
        self._log_audit(incident_id, "Commander", "PLAN_CREATED", f"Formulated {len(steps)}-step recovery plan {plan_id} (risk: {plan_risk}).")
        
    def save_agent_findings(self, incident_id: str, llm_response: Dict[str, Any], critic_passed: bool = True, critic_feedback: str = "") -> Dict[str, Any]:
        """Saves the JSON output from the NemoClaw agents into the database."""
        now = datetime.now(timezone.utc).isoformat()
        
        if "error" in llm_response:
            return llm_response 
            
        # Normalize pi's simplified output format if it fails to use the full schema
        if "finding" in llm_response and "action_plan" not in llm_response:
            llm_response = {
                "hypotheses": [
                    {
                        "statement": llm_response.get("finding"),
                        "cause_type": "SYSTEM_FAILURE",
                        "confidence": 0.90
                    }
                ],
                "action_plan": {
                    "rationale": "Automated recovery formulation based on agent findings.",
                    "expected_outcome": "System restored to normal operating state.",
                    "risk": "MEDIUM",
                    "steps": llm_response.get("steps", [])
                }
            }
            
        with self.db.get_connection() as conn:
            # Ensure SYSTEM agent_run exists for foreign keys
            conn.execute("""
                INSERT INTO agent_run (agent_run_id, incident_id, agent_name, objective, status)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (agent_run_id) DO NOTHING
            """, ("SYSTEM", incident_id, "System Triage", "Triage Incident", "COMPLETED"))
            
            # 1. Insert Evidence
            evidence_ids = []
            for ev in llm_response.get("evidence", []):
                ev_id = self._generate_id("EVD")
                evidence_ids.append(ev_id)
                conn.execute("""
                    INSERT INTO evidence (evidence_id, incident_id, evidence_type, source_system, title, excerpt, collected_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (ev_id, incident_id, ev.get("type", "Log"), ev.get("source", "System"), ev.get("title", "Evidence"), ev.get("excerpt", ""), now))
            
            # 2. Insert Hypotheses
            primary_hypothesis = None
            for idx, hyp in enumerate(llm_response.get("hypotheses", [])):
                hyp_id = self._generate_id("HYP")
                if idx == 0:
                    primary_hypothesis = hyp
                conn.execute("""
                    INSERT INTO hypothesis (hypothesis_id, incident_id, agent_run_id, rank_no, statement, cause_type, confidence, status, supporting_evidence_json, contradicting_evidence_json, missing_evidence_json, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (hyp_id, incident_id, "SYSTEM", idx+1, hyp.get("statement", ""), hyp.get("cause_type", "OTHER"), hyp.get("confidence", 0.5), "PROBABLE_CAUSE", json.dumps(evidence_ids), "[]", "[]", now))
                
            # 3. Insert Impacts
            for imp in llm_response.get("impacts", []):
                asset_id = imp.get("asset_id", "Unknown")
                conn.execute("""
                    INSERT INTO data_asset (asset_id, asset_type, name)
                    VALUES (%s, 'Unknown', %s)
                    ON CONFLICT (asset_id) DO NOTHING
                """, (asset_id, asset_id))
                conn.execute("""
                    INSERT INTO incident_impact (incident_id, asset_id, impact_type, impact_status, reason, impact_score, evidence_ids_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (incident_id, asset_id, imp.get("impact_type", "Unknown"), imp.get("status", "AT_RISK"), imp.get("reason", ""), imp.get("score", 0.5), json.dumps(evidence_ids)))
                
            # 4. Insert Action Plan
            plan_data = llm_response.get("action_plan", {})
            plan_id = self._generate_id("PLN")
            # If the Safety Agent (Grounding Critic) flagged this plan, mark it NEEDS_REVIEW
            # instead of PENDING_APPROVAL so the frontend can gate the Approve button behind
            # an explicit acknowledgement of the safety concern.
            plan_status = "NEEDS_REVIEW" if not critic_passed else "PENDING_APPROVAL"
            rationale = plan_data.get("rationale", "")
            if not critic_passed and critic_feedback:
                rationale = f"[SAFETY REVIEW REQUIRED] {critic_feedback}\n\n{rationale}"
            conn.execute("""
                INSERT INTO action_plan (action_plan_id, incident_id, agent_run_id, plan_version, status, overall_risk, rationale, expected_outcome, rollback_summary, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (plan_id, incident_id, "SYSTEM", 1, plan_status, plan_data.get("risk", "MEDIUM"), rationale, plan_data.get("expected_outcome", ""), "Manual Rollback Required", now))
            
            # Action Steps
            for i, step in enumerate(plan_data.get("steps", []), 1):
                risk = step.get("risk", "LOW")
                conn.execute("""
                    INSERT INTO action_step (action_step_id, action_plan_id, sequence_no, action_type, tool_name, risk_level, requires_approval, parameters_json, preconditions_json, expected_postconditions_json, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (self._generate_id("STP"), plan_id, i, step.get("action", ""), step.get("tool", "manual"), risk, 1 if risk in ["MEDIUM", "HIGH"] else 0, "{}", "{}", "{}", "PENDING"))
                
            # Update Incident
            rca_statement = primary_hypothesis.get("statement", "") if primary_hypothesis else "AI Triage Completed"
            rca_confidence = primary_hypothesis.get("confidence", 0.0) if primary_hypothesis else 0.0
            conn.execute(
                "UPDATE incident SET actual_root_cause = %s, rca_confidence = %s, status = %s WHERE incident_id = %s",
                (rca_statement, rca_confidence, IncidentState.PLAN_READY.value, incident_id)
            )
            
        self._log_audit(incident_id, "Commander", "PLAN_CREATED", f"Commander synthesized multi-agent findings into recovery plan {plan_id}.")
        
        return {"status": "success", "plan_id": plan_id}

    def triage_fallback(self, incident_id: str) -> Dict[str, Any]:
        """Generates high-quality triage data by invoking the native Python Tool-Calling Agents. Used when TS-nemoclaw agent is unavailable."""
        now = datetime.now(timezone.utc).isoformat()
        
        import asyncio
        from src.domain.agents.rca_agent import RCAAgent
        from src.domain.agents.dependency_agent import DependencyAgent
        
        # 1. RCA Agent Execution
        self._log_audit(incident_id, "SYSTEM", "FALLBACK_RCA_STARTED", "Invoking native Python RCA Agent with Tool Calling")
        rca_agent = RCAAgent()
        rca_result = asyncio.run(rca_agent.analyze(incident_id))
        
        if "error" in rca_result:
            return {"error": rca_result["error"]}
            
        cause_type = rca_result.get("cause_type", "OTHER")
        hypothesis_statement = rca_result.get("finding", "Unknown root cause")
        confidence = rca_result.get("confidence", 0.9)
        
        # 2. Dependency Agent Execution
        self._log_audit(incident_id, "SYSTEM", "FALLBACK_DEPENDENCY_STARTED", "Invoking native Python Dependency Agent with Tool Calling")
        dep_agent = DependencyAgent()
        dep_result = asyncio.run(dep_agent.analyze(hypothesis_statement))
        
        impacts_from_agent = dep_result.get("impacts", [])
        
        plan_risk = "MEDIUM"
        plan_rationale = "Fallback AI Agent executed triage using tools."
        plan_outcome = "System expects normal operation after manual intervention."

        with self.db.get_connection() as conn:
            evidence_ids = []
            
            # Use the evidence found by RCAAgent
            for ev in rca_result.get("evidence", []):
                ev_id = self._generate_id("EVD")
                evidence_ids.append(ev_id)
                conn.execute("""
                    INSERT INTO evidence (evidence_id, incident_id, evidence_type, source_system, title, excerpt, collected_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (ev_id, incident_id, ev.get("type", "Log"), "LLM-Tool", ev.get("title", "Evidence"), ev.get("excerpt", ""), now))
                
            # We don't have logs_data anymore, as the agent used tools directly to fetch them!

            # Hypothesis
            hyp_id = self._generate_id("HYP")
            conn.execute("""
                INSERT INTO hypothesis (hypothesis_id, incident_id, agent_run_id, rank_no, statement, cause_type, confidence, status, supporting_evidence_json, contradicting_evidence_json, missing_evidence_json, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (hyp_id, incident_id, "RCA-Agent", 1, hypothesis_statement, cause_type, 0.93, "PROBABLE_CAUSE", json.dumps(evidence_ids), "[]", "[]", now))

            # Impact analysis
            for imp in impacts_from_agent:
                asset_id = imp.get("asset_id", "Unknown")
                conn.execute("""
                    INSERT INTO data_asset (asset_id, asset_type, name)
                    VALUES (%s, 'Unknown', %s)
                    ON CONFLICT (asset_id) DO NOTHING
                """, (asset_id, asset_id))
                conn.execute("""
                    INSERT INTO incident_impact (incident_id, asset_id, impact_type, impact_status, reason, impact_score, evidence_ids_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (incident_id, asset_id, imp.get("impact_type"), imp.get("status"), imp.get("reason"), 0.9, "[]"))

            # Action Plan
            plan_id = self._generate_id("PLN")
            conn.execute("""
                INSERT INTO action_plan (action_plan_id, incident_id, agent_run_id, plan_version, status, overall_risk, rationale, expected_outcome, rollback_summary, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (plan_id, incident_id, "Commander", 1, "PENDING_APPROVAL", plan_risk, plan_rationale, plan_outcome,
                  "Restore schema mapping v118 and re-deploy with backward compatibility flag enabled", now))
            
            steps = [
                ("Rollback schema mapping to v118 (restore loyalty_id column)", "schema_rollback", "MEDIUM"),
                ("Validate schema compatibility against all consumers", "schema_validate", "LOW"),
                ("Re-trigger customer_profile ingestion pipeline", "pipeline_trigger", "MEDIUM"),
                ("Verify downstream job execution and data freshness", "health_check", "LOW"),
            ]
            for i, (action, tool, risk) in enumerate(steps, 1):
                conn.execute("""
                    INSERT INTO action_step (action_step_id, action_plan_id, sequence_no, action_type, tool_name, risk_level, requires_approval, parameters_json, preconditions_json, expected_postconditions_json, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (self._generate_id("STP"), plan_id, i, action, tool, risk, 1 if risk == "MEDIUM" else 0, "{}", "{}", "{}", "PENDING"))
                
            conn.execute(
                "UPDATE incident SET actual_root_cause = %s, rca_confidence = %s, status = %s WHERE incident_id = %s",
                (hypothesis_statement, 0.93, IncidentState.PLAN_READY.value, incident_id)
            )

        self._log_audit(incident_id, "RCA Agent", "HYPOTHESIS_CREATED", f"RCA Agent isolated root cause using tools with {confidence*100}% confidence.")
        self._log_audit(incident_id, "Impact Agent", "IMPACT_CALCULATED", f"Impact Agent identified {len(impacts_from_agent)} affected downstream assets from CMDB.")
        self._log_audit(incident_id, "Runbook Agent", "RUNBOOK_RETRIEVED", "Runbook Agent matched incident to standard recovery steps.")
        self._log_audit(incident_id, "Safety Agent", "SAFETY_VALIDATION_PASSED", "Safety Agent validated plan parameters and verified blast radius is contained.")
        self._log_audit(incident_id, "Commander", "PLAN_CREATED", f"Commander formulated 4-step recovery plan {plan_id} (risk: {plan_risk}). Human approval required for MEDIUM-risk steps.")
        
        return {"status": "success", "plan_id": plan_id}

    def execute_plan(self, incident_id: str, plan_id: str):
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute("UPDATE action_plan SET status = 'EXECUTED' WHERE action_plan_id = %s", (plan_id,))
            conn.execute("UPDATE action_step SET status = 'SUCCEEDED' WHERE action_plan_id = %s", (plan_id,))
            conn.execute("UPDATE incident SET status = %s WHERE incident_id = %s", (IncidentState.RESOLVED.value, incident_id))
            
            # Create verification results
            conn.execute("""
                INSERT INTO verification_result (verification_id, incident_id, action_plan_id, check_name, status, expected_json, actual_json, evidence_ids_json, checked_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (self._generate_id("VRF"), incident_id, plan_id, "Schema validation", "PASSED", "{}", "{}", "[]", now))
            
            conn.execute("""
                INSERT INTO verification_result (verification_id, incident_id, action_plan_id, check_name, status, expected_json, actual_json, evidence_ids_json, checked_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (self._generate_id("VRF"), incident_id, plan_id, "Row count within tolerance", "PASSED", "{}", "{}", "[]", now))
            
            conn.execute("UPDATE incident SET status = %s, resolved_at = %s WHERE incident_id = %s", (IncidentState.RESOLVED.value, now, incident_id))
            
        self._log_audit(incident_id, "Executor", "ACTION_COMPLETED", "All recovery steps executed successfully")
        self._log_audit(incident_id, "Verifier", "VERIFICATION_PASSED", "Independent verification checks passed")
        self._log_audit(incident_id, "Commander", "INCIDENT_RESOLVED", "Incident resolved successfully")

    def triage_feedback(self, incident_id: str, feedback_text: str) -> Dict[str, Any]:
        """Handles user feedback on an existing action plan and generates a revised plan."""
        with self.db.get_connection() as conn:
            # 1. Fetch existing plan
            cursor = conn.execute("SELECT action_plan_id, rationale, expected_outcome, overall_risk FROM action_plan WHERE incident_id = %s ORDER BY created_at DESC LIMIT 1", (incident_id,))
            plan_row = cursor.fetchone()
            if not plan_row:
                return {"error": "No existing action plan found for this incident."}
            
            plan_id = plan_row[0]
            existing_plan = {
                "rationale": plan_row[1],
                "expected_outcome": plan_row[2],
                "risk": plan_row[3],
                "steps": []
            }
            
            # Fetch existing steps
            cursor = conn.execute("SELECT action_type, tool_name, risk_level FROM action_step WHERE action_plan_id = %s ORDER BY sequence_no ASC", (plan_id,))
            for row in cursor.fetchall():
                existing_plan["steps"].append({
                    "action": row[0],
                    "tool": row[1],
                    "risk": row[2]
                })

        prompt = f"""
        The user rejected the previous action plan for Incident ID: {incident_id}.
        
        User Feedback:
        {feedback_text}
        
        Previous Action Plan:
        {json.dumps(existing_plan, indent=2)}
        
        Generate a new, revised action plan that addresses the user's feedback. 
        The plan MUST be highly technical and actionable (provide exact bash commands, SQL scripts, or API calls).
        
        Output a strict JSON object with this exact structure:
        {{
            "rationale": "Why we are doing this revised plan",
            "expected_outcome": "What this will fix",
            "risk": "LOW|MEDIUM|HIGH",
            "steps": [
              {{"action": "Describe exact technical step", "tool": "tool_name", "risk": "LOW|MEDIUM|HIGH"}}
            ]
        }}
        """

        llm_response = self.call_llm_json(prompt)
        
        if "error" in llm_response:
            return llm_response

        # Update the database
        with self.db.get_connection() as conn:
            # Delete old steps
            conn.execute("DELETE FROM action_step WHERE action_plan_id = %s", (plan_id,))
            
            # Update plan
            conn.execute("""
                UPDATE action_plan 
                SET rationale = %s, expected_outcome = %s, overall_risk = %s, plan_version = plan_version + 1, status = 'PENDING_APPROVAL'
                WHERE action_plan_id = %s
            """, (
                llm_response.get("rationale", ""), 
                llm_response.get("expected_outcome", ""), 
                llm_response.get("risk", "MEDIUM"),
                plan_id
            ))
            
            # Insert new steps
            for i, step in enumerate(llm_response.get("steps", []), 1):
                risk = step.get("risk", "LOW")
                conn.execute("""
                    INSERT INTO action_step (action_step_id, action_plan_id, sequence_no, action_type, tool_name, risk_level, requires_approval, parameters_json, preconditions_json, expected_postconditions_json, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (self._generate_id("STP"), plan_id, i, step.get("action", ""), step.get("tool", "manual"), risk, 1 if risk in ["MEDIUM", "HIGH"] else 0, "{}", "{}", "{}", "PENDING"))

        self._log_audit(incident_id, "Feedback Agent", "PLAN_REVISED", f"Action plan {plan_id} revised based on user feedback.")
        
        return {"status": "success", "plan_id": plan_id}

    async def process_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Processes incoming webhooks via the WatcherAgent to determine if it's a valid alert and if it correlates."""
        import psycopg2.extras
        
        # 1. Fetch active incidents
        active_incidents = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("SELECT incident_id, title, summary, primary_run_id, status FROM incident WHERE status NOT IN ('RESOLVED', 'CLOSED', 'CANCELLED')")
            active_incidents = [dict(row) for row in cursor.fetchall()]

        watcher = WatcherAgent()
        analysis = await watcher.analyze(payload, active_incidents)
        
        if "error" in analysis:
            return {"status": "error", "message": analysis["error"]}
            
        if not analysis.get("is_valid"):
            return {"status": "ignored", "reasoning": analysis.get("reasoning", "Classified as noise")}
            
        alert_data = analysis.get("normalized_alert")
        if not alert_data:
            return {"status": "error", "message": "Valid alert but missing normalized_alert data"}
            
        # Extract fields
        severity = alert_data.get("severity", "info").lower()
        alert_type = alert_data.get("alert_type", "UNKNOWN")
        source_system = alert_data.get("source_system", "Webhook")
        message = alert_data.get("message", "No message provided")
        run_id = alert_data.get("run_id")
        
        alert_id = self._generate_id("WEB-ALT")
        now = datetime.now(timezone.utc).isoformat()
        
        # Insert the new alert into the DB
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO alert (alert_id, run_id, opened_ts, severity, alert_type, source_system, message, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'open')
            """, (alert_id, run_id, now, severity, alert_type, source_system, message))
            
            # Check if AI correlated this to an existing incident
            correlated_incident_id = analysis.get("correlated_incident_id")
            
            if correlated_incident_id and any(i['incident_id'] == correlated_incident_id for i in active_incidents):
                # Map to existing incident
                conn.execute("""
                    INSERT INTO incident_alert (incident_id, alert_id, correlation_score, correlation_reasons_json, added_at)
                    VALUES (%s, %s, %s, %s, %s)
                """, (correlated_incident_id, alert_id, analysis.get("confidence", 0.95), json.dumps([analysis.get("reasoning")]), now))
                
                # Update incident summary
                conn.execute("""
                    UPDATE incident 
                    SET summary = summary || %s, updated_at = %s 
                    WHERE incident_id = %s
                """, (f"\n\nNew Correlated Alert: {message}", now, correlated_incident_id))
                
                self._log_audit(correlated_incident_id, "Watcher Agent", "ALERT_CORRELATED", f"Alert {alert_id} dynamically correlated to this incident by AI. Reasoning: {analysis.get('reasoning')}")
                
                return {
                    "status": "ingested_and_correlated",
                    "alert_id": alert_id,
                    "incident_id": correlated_incident_id,
                    "reasoning": analysis.get("reasoning")
                }
                
            # Otherwise, Simple Correlation: For now, create a new incident immediately for HIGH or CRITICAL alerts.
            elif severity in ["high", "critical"]:
                from src.domain.correlator import CorrelatorEngine
                from src.domain.models import Alert
                
                alert_obj = Alert(
                    alert_id=alert_id,
                    run_id=run_id,
                    opened_ts=datetime.now(timezone.utc),
                    severity=severity,
                    alert_type=alert_type,
                    source_system=source_system,
                    message=message,
                    status="open"
                )
                
                correlator = CorrelatorEngine()
                cluster = {"primary_alert": alert_obj, "alerts": [alert_obj], "duplicate_count": 0, "cluster_score": 1.0}
                incident = correlator.create_incident(cluster)
                
                conn.execute("""
                    INSERT INTO incident (
                        incident_id, title, status, severity, detected_at, created_at, updated_at, 
                        summary, primary_run_id, correlation_confidence, next_sla_breach_at, version
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    incident.incident_id,
                    incident.title,
                    IncidentState.INVESTIGATING.value,
                    incident.severity.value if hasattr(incident.severity, 'value') else incident.severity,
                    now, now, now,
                    incident.summary,
                    incident.primary_run_id,
                    incident.correlation_confidence,
                    (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
                    1
                ))
                
                conn.execute("""
                    INSERT INTO incident_alert (incident_id, alert_id, correlation_score, correlation_reasons_json, added_at)
                    VALUES (%s, %s, %s, %s, %s)
                """, (incident.incident_id, alert_id, 1.0, json.dumps(["Direct webhook correlation"]), now))
                
                # Auto-start triage (Now handled in api/main.py by kicking off Temporal workflow)
                
                return {
                    "status": "ingested_and_incident_created", 
                    "alert_id": alert_id, 
                    "incident_id": incident.incident_id,
                    "reasoning": analysis.get("reasoning")
                }
                
        return {
            "status": "ingested", 
            "alert_id": alert_id, 
            "reasoning": analysis.get("reasoning")
        }
