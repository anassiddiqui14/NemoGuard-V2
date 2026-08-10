from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime
from .enums import IncidentState, Severity, ToolRisk, HypothesisStatus

class Incident(BaseModel):
    incident_id: str
    title: str
    status: IncidentState
    severity: Severity
    detected_at: datetime
    created_at: datetime
    updated_at: datetime
    summary: Optional[str] = None
    primary_job_id: Optional[str] = None
    primary_run_id: Optional[str] = None
    owner_team: Optional[str] = None
    resolved_at: Optional[datetime] = None
    correlation_confidence: Optional[float] = None
    rca_confidence: Optional[float] = None
    next_sla_breach_at: Optional[datetime] = None
    actual_root_cause: Optional[str] = None
    resolution_summary: Optional[str] = None
    version: int = 1

class Alert(BaseModel):
    alert_id: str
    run_id: Optional[str] = None
    opened_ts: datetime
    severity: str
    alert_type: str
    source_system: str
    message: str
    status: str

class AgentRun(BaseModel):
    agent_run_id: str
    incident_id: str
    agent_name: str
    objective: str
    status: str
    parent_agent_run_id: Optional[str] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    token_input: Optional[int] = None
    token_output: Optional[int] = None
    latency_ms: Optional[int] = None
    error_message: Optional[str] = None

class Evidence(BaseModel):
    evidence_id: str
    incident_id: str
    tool_call_id: Optional[str] = None
    evidence_type: str
    source_system: str
    source_record_id: Optional[str] = None
    title: str
    excerpt: str
    occurred_at: Optional[datetime] = None
    collected_at: datetime
    reliability: float = 1.0
    metadata_json: Optional[str] = None

class Hypothesis(BaseModel):
    hypothesis_id: str
    incident_id: str
    agent_run_id: str
    rank_no: int
    statement: str
    confidence: float
    status: HypothesisStatus
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    cause_type: Optional[str] = None
    created_at: datetime

class IncidentImpact(BaseModel):
    incident_id: str
    asset_id: str
    impact_type: str
    impact_status: str
    reason: str
    expected_breach_at: Optional[datetime] = None
    impact_score: float
    evidence_ids: List[str] = Field(default_factory=list)

class ActionPlan(BaseModel):
    action_plan_id: str
    incident_id: str
    agent_run_id: str
    plan_version: int
    status: str
    overall_risk: ToolRisk
    rationale: str
    expected_outcome: str
    rollback_summary: str
    created_at: datetime
    runbook_id: Optional[str] = None

class ActionStep(BaseModel):
    action_step_id: str
    action_plan_id: str
    sequence_no: int
    action_type: str
    tool_name: str
    risk_level: ToolRisk
    requires_approval: bool
    parameters_json: str
    preconditions_json: str
    expected_postconditions_json: str
    rollback_tool_name: Optional[str] = None
    rollback_parameters_json: Optional[str] = None
    status: str

class Approval(BaseModel):
    approval_id: str
    incident_id: str
    action_plan_id: str
    requested_at: datetime
    expires_at: datetime
    decision: str
    decided_at: Optional[datetime] = None
    approver_id: Optional[str] = None
    approver_role: Optional[str] = None
    comment: Optional[str] = None
    plan_hash: str

class ActionExecution(BaseModel):
    action_execution_id: str
    action_step_id: str
    approval_id: Optional[str] = None
    idempotency_key: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    before_state_json: Optional[str] = None
    after_state_json: Optional[str] = None
    result_json: Optional[str] = None
    error_message: Optional[str] = None

class VerificationResult(BaseModel):
    verification_id: str
    incident_id: str
    action_plan_id: str
    check_name: str
    status: str
    expected_json: str
    actual_json: str
    evidence_ids: List[str] = Field(default_factory=list)
    checked_at: datetime

class AuditEvent(BaseModel):
    audit_event_id: str
    incident_id: Optional[str] = None
    actor_type: str
    actor_id: str
    event_type: str
    event_summary: str
    details_json: Optional[str] = None
    created_at: datetime
