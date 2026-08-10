# NemoClaw Network and Architecture Specification

This document provides a detailed, technical breakdown of the NemoClaw agentic flow based on the multi-agent network architecture. It is designed to be handed off to engineering teams for implementation and integration with the NVIDIA Nemotron model.

## Core System Overview
The system is an autonomous, event-driven agentic framework for incident response. It ingests raw telemetry, normalizes it, and routes it to an orchestration layer which delegates investigative tasks to parallel sub-agents. The results are aggregated to propose actionable recovery plans to human operators.

---

## 1. Alert Streamer / Scenario Lab
**Responsibility**: The ingestion layer. Collects raw alerts from the custom **Synthetic Scenario Generator**, standardizes them into a common schema, and streams them to the datastore.
*   **Sources**: Synthetic Scenario Lab (Internal Pipeline Demo/Testing Framework).
*   **Output Schema (Normalized Alert)**:
    ```json
    {
      "alertId": "DEMO-ALT-001",
      "source": "Airflow",
      "service": "customer_profile_ingestion",
      "type": "SCHEMA_COLUMN_MISSING",
      "timestamp": "2026-08-06T09:30:00Z",
      "details": {"severity": "critical", "status": "open"}
    }
    ```

## 2. Orchestrator & Triage Fallback
**Responsibility**: The central brain. It groups related alerts into an official Incident via a Correlator Engine, and triggers the AI Agent Network to generate evidence and hypotheses.
*   **Core Actions**:
    *   Create Incident in the datastore based on clustered alerts.
    *   Initialize the `audit_event` stream to inform the UI that investigation is underway.
    *   Invoke the Agent Network.
    *   *Fallback*: Generate highly deterministic synthetic triage data if the LLM is unavailable to ensure the demo continues.

## 3. Sub-Agents (The NemoClaw Network)
**Responsibility**: Specialized, concurrent workers that execute the Commander's investigation plan. They all share standard context (the Incident ID, recent logs, and dependent topologies).

### 3A. Root Cause Agent (RCA)
*   **Role**: Analyzes structured logs, execution traces, and recent anomaly patterns to pinpoint the root cause (e.g. "Schema validation failed due to missing loyalty_id").
*   **Output**: Generates `Hypothesis` entries mapping the `cause_type`, `statement`, and `confidence_score`.

### 3B. Impact Agent (Blast Radius)
*   **Role**: Analyzes the dependency graph of the failing job to evaluate downstream pipelines, data products, and dashboards.
*   **Output**: Generates `Evidence` entries for the dynamic causal chain and computes `BusinessImpact` (e.g., number of blocked jobs, dashboards at risk, SLA runway).

### 3C. Runbook Agent
*   **Role**: Scans existing knowledge bases to match the incident signature to approved operational runbooks. Formulates precise recovery steps.
*   **Output**: Drafts the initial `ActionPlan` and `ActionSteps`.

### 3D. Safety / Verifier Agent
*   **Role**: Acts as a strict validation layer over the proposed `ActionPlan`. Ensures the runbook steps do not introduce higher risk or destructive mutations without authorization.
*   **Output**: Attaches a risk score (e.g. `LOW`, `HIGH`) and justification to the ActionPlan, advancing the state to `PLAN_READY`.

---

## 4. Supporting Dimensions (Information & Context)
**Responsibility**: The read-only data plane providing external context via MCP-style tools to both the Orchestrator and Sub-Agents.
*   **Data Domains**: 
    *   `job` & `dependency` Topology Database
    *   `log_event` trace logs
    *   `incident_alert` associations

## 5. Human-in-the-Loop (Approval Gate)
**Responsibility**: Synthesizes the parallel findings from all sub-agents into a final, human-readable recovery plan presented on the React Dashboard.
*   **Core Actions**:
    *   Aggregate findings from all sub-agents into the Incident Modal.
    *   Present the Action Steps clearly to the Operator.
    *   Await human authorization (`Execute Plan`).
    *   Allow the human to provide feedback and tune the prompts if the plan is rejected.

## 6. Feedback & Continuous Learning Loop
**Responsibility**: Analyzes the operator's feedback if a plan is rejected and dynamically regenerates a strictly tailored action plan using the updated context.
*   **Actions**:
    *   Injects the user's rejection text (`feedback_text`) directly into the Agent's system prompt.
    *   Updates runbooks dynamically for this specific incident.
