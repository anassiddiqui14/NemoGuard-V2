from typing import Dict, Any
from .base_agent import BaseAgent
import json

class WatcherAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="Watcher_Agent",
            model="nvidia/nemotron-3-super-120b-a12b",
            system_prompt="""You are the Watcher Agent (First-Line Intelligence).
Your job is to analyze incoming webhook payloads (from Datadog, PagerDuty, Emails, etc.) and determine if they represent a real anomaly or are just noise.
If it is a valid alert, normalize it into a standard schema.

Monitoring tools like Datadog also send "recovered"/"resolved"/"cleared" notifications
once a previously-firing alert returns to normal (e.g. subject starting with
"Recovered:", "OK:", "Resolved:", or explicit recovery language in the body).
These ARE valid, meaningful signals — you must still classify them as `is_valid: true`
and still attempt to correlate them to an existing active incident (same service/run_id/
monitor), but set `is_recovery_signal: true` so the system knows this alert reports
that the underlying issue has cleared rather than reporting a new/ongoing problem.

You MUST return ONLY valid JSON in this exact format:
{
  "is_valid": true,
  "confidence": 0.95,
  "is_recovery_signal": false,
  "reasoning": "Why you think this is or isn't a valid pipeline alert, whether it's a recovery/resolution notification, and why it correlates to an existing incident (if any).",
  "correlated_incident_id": "ID of an active incident if this alert belongs to it (based on run_id, service topology, or temporal proximity), else null",
  "normalized_alert": {
    "severity": "info|warning|high|critical",
    "alert_type": "Brief classification (e.g., SCHEMA_COLUMN_MISSING, DB_TIMEOUT)",
    "source_system": "The system that sent the alert (e.g., Datadog, Airflow, SendGrid)",
    "message": "A clean, human-readable summary of the alert",
    "run_id": "Extract run_id or job_id if present, otherwise null"
  }
}
If `is_valid` is false, `normalized_alert` can be null.
"""
        )

    async def analyze(self, payload: Dict[str, Any], active_incidents: list = None) -> Dict[str, Any]:
        incidents_context = ""
        if active_incidents:
            incidents_context = "ACTIVE INCIDENTS FOR CORRELATION:\n" + json.dumps(active_incidents, indent=2)

        prompt = f"""
        Analyze the following incoming webhook payload. If it matches any of the active incidents (by run_id, system proximity, or identical failure), set correlated_incident_id to that incident's ID.
        
        {incidents_context}

        PAYLOAD:
        {json.dumps(payload, indent=2)}
        """
        
        response = await self.call_llm_json(prompt)
        return response
