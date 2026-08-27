from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict


class HistoricalIncident(BaseModel):
    id: str
    external_incident_id: Optional[str] = None
    source_system: str
    opened_at: str
    resolved_at: Optional[str] = None
    service: Optional[str] = None
    pipeline: Optional[str] = None
    environment: Optional[str] = None
    severity: Optional[str] = None
    title: str
    created_at: str
    created_by: Optional[str] = None


class HistoricalIncidentSnapshot(BaseModel):
    id: str
    historical_incident_id: str
    snapshot_type: str
    snapshot_timestamp: str
    source_reference: Optional[str] = None
    payload_json: str
    created_at: str


class HistoricalIncidentGroundTruth(BaseModel):
    historical_incident_id: str
    root_cause: str
    cause_type: Optional[str] = None
    actual_recovery: Optional[str] = None
    actual_impacted_assets_json: Optional[str] = None
    actual_business_impact: Optional[str] = None
    actual_resolution_time_seconds: Optional[float] = None
    postmortem_reference: Optional[str] = None
    created_at: str


class HistoricalIncidentReplay(BaseModel):
    id: str
    historical_incident_id: str
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    prompt_version: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    status: str = "PENDING"
    error_message: Optional[str] = None
    created_by: Optional[str] = None


class HistoricalIncidentReplayResult(BaseModel):
    replay_id: str
    top_hypothesis: Optional[str] = None
    top_hypothesis_cause_type: Optional[str] = None
    top_hypothesis_score: Optional[float] = None
    top_3_hypotheses: List[Dict[str, Any]] = Field(default_factory=list)
    selected_runbook: Optional[str] = None
    recommended_plan: Dict[str, Any] = Field(default_factory=dict)
    tool_calls: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    elapsed_seconds: Optional[float] = None
    top1_correct: Optional[bool] = None
    top3_correct: Optional[bool] = None
    cause_family_correct: Optional[bool] = None
    scored_at: Optional[str] = None
