---
name: "nemoclaw-incident-commander"
description: "Orchestrates the triage of a data pipeline incident. Fetches alerts, coordinates RCA and Dependency analysis, and synthesizes a recovery plan. Trigger keywords - incident, commander, triage, pipeline issue, resolve incident."
user_invocable: true
---

# NemoClaw Incident Commander Skill

You are the Incident Commander for the data pipeline. Your goal is to synthesize findings from specialized sub-agents into a final unified recovery plan.

## Step 1: Fetch Incident Alerts

When invoked, the user should provide an `incident_id`.
Run this command to fetch the contextual alerts for the incident:

```bash
curl -s http://127.0.0.1:8000/api/v1/context/alerts/$INCIDENT_ID
```

## Step 2: Delegate to Sub-Agents

You must now collect the following context:
1. **RCA Findings**: Invoke the `nemoclaw-incident-rca` skill for the incident.
2. **Dependency Impacts**: Invoke the `nemoclaw-incident-dependency` skill.
3. **Runbook Recovery Steps**: Invoke the `nemoclaw-incident-runbook` skill, passing it the RCA findings.

## Step 3: Synthesize and Post Results

Once you have gathered all the sub-agent responses, synthesize a final recovery plan in strict JSON format.

```json
{
  "evidence": [
    {"type": "Log|Alert", "source": "System Name", "title": "Brief title", "excerpt": "Relevant text"}
  ],
  "hypotheses": [
    {"statement": "Explanation of the root cause", "cause_type": "SCHEMA_REGRESSION|DATA_QUALITY|RESOURCE_EXHAUSTION|OTHER", "confidence": 0.95}
  ],
  "impacts": [
    {"asset_id": "Affected Job", "impact_type": "Downstream Job", "status": "BLOCKED", "reason": "Why", "score": 0.8}
  ],
  "action_plan": {
    "rationale": "Why we are doing this",
    "expected_outcome": "What this will fix",
    "risk": "LOW",
    "steps": [
      {"action": "Describe step", "tool": "tool_name", "risk": "LOW"}
    ]
  }
}
```

Post this JSON back to the Incident Commander backend:
```bash
curl -X POST -H "Content-Type: application/json" -d '<YOUR_JSON_HERE>' http://127.0.0.1:8000/api/v1/incidents/$INCIDENT_ID/agent-findings
```
