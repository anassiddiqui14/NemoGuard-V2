# NemoClaw Agent Architecture & Configuration

This document describes the individual AI agents within the NemoGuard Pipeline Copilot, their configuration, their interactions, and how they integrate within the orchestrator app.

---

## 1. The Agent Base Class (`BaseAgent`)
**Location:** `src/domain/agents/base_agent.py`

All agents in the NemoClaw network inherit from `BaseAgent`. This class handles the core LLM integration.
- **Model:** Currently configured to use `nvidia/nemotron-3-super-120b-a12b`.
- **API Setup:** Uses the NVIDIA NIM API (`https://integrate.api.nvidia.com/v1/chat/completions`). It authenticates via the `NVIDIA_API_KEY` environment variable.
- **Async Execution:** Provides the `call_llm_json(prompt)` method, which wraps synchronous REST calls in an `asyncio` execution thread to ensure the FastAPI server remains non-blocking during agent inference.
- **Output Parsing:** Enforces strict JSON return formats. It actively strips Markdown wrappers (e.g. ` ```json `) to prevent parsing crashes.

---

## 2. Specialized Sub-Agents

### A. RCA Agent (Root Cause Analysis)
**Location:** `src/domain/agents/rca_agent.py`
- **Responsibility:** Ingests the incident alerts and recent execution logs (specifically filtering for `ERROR` or `WARN` levels) to determine the exact root cause of the incident.
- **Configuration (System Prompt):** Strictly instructed to return JSON containing the `finding`, `cause_type` (e.g. `SCHEMA_REGRESSION`, `DATA_QUALITY`), a confidence score, and specific `evidence` arrays citing the relevant logs or alerts.
- **Integration:** Triggered early in the orchestration loop. Its findings are displayed in the UI as the active "Causal Chain".

### B. Dependency Agent (Blast Radius)
**Location:** `src/domain/agents/dependency_agent.py`
- **Responsibility:** Evaluates downstream systems and pipelines blocked or put at risk by the incident.
- **Configuration:** Reads the topology map from `data/mock_dimensions/cmdb.json`. The system prompt asks it to analyze the active alerts against the CMDB to determine affected `asset_id`s, `status` (BLOCKED vs AT_RISK), and impact type.
- **Integration:** The results drive the "Business Impact" section of the frontend, populating the count of "Affected Assets" and "SLA Runways".

### C. Runbook Agent (Recovery Strategy)
**Location:** `src/domain/agents/runbook_agent.py`
- **Responsibility:** Scans existing operational runbooks to formulate a targeted recovery strategy.
- **Configuration:** Reads the available operational playbooks from `data/mock_dimensions/runbooks.json`. It takes both the active alerts and the preliminary findings from the **RCA Agent** as input prompts.
- **Integration:** Formulates a list of actionable recovery steps (e.g., "Rollback Deployment") and risk assessments.

### D. Commander Agent (Orchestration & Synthesis)
**Location:** `src/domain/agents/commander_agent.py`
- **Responsibility:** The executive decision-maker. It takes the independent, parallel findings of all the sub-agents and synthesizes them into a single, cohesive incident recovery package.
- **Configuration:** Instructed to output the exact final JSON payload expected by the frontend API. This includes merging the RCA, Dependency, and Runbook outputs into a single payload with `evidence`, `hypotheses`, `impacts`, and `action_plan`.
- **Integration:** Called via the `synthesize` method at the end of the orchestration pipeline. The output of the Commander is what actually drives the "Plan Approval Modal" on the React dashboard.

---

## 3. Integration & Workflow

When a user initiates triage in the UI, the backend `orchestrator.py` module triggers the agents in the following sequence:

1. **Parallel Investigation:** The `RCAAgent` and `DependencyAgent` are invoked simultaneously using `asyncio.gather()` to minimize latency.
2. **Sequential Strategy:** The `RunbookAgent` is invoked after the `RCAAgent` finishes, as it relies on the root cause finding to select the correct playbook.
3. **Synthesis:** The `CommanderAgent` takes the outputs of all three sub-agents and synthesizes the final incident state.
4. **Audit Streaming:** Throughout this process, each agent writes its actions and reasoning logs to the `audit_event` database table. The React frontend actively listens to these events via SSE (Server-Sent Events) and renders them in the "Agent Activity & Tool Trace" console.
