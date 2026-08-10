from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class GetRecentDeploymentsInput(BaseModel):
    service_id: str
    lookback_hours: int = Field(default=24, ge=1, le=168)

class DeploymentRecord(BaseModel):
    deployment_id: str
    version: str
    deployed_at: datetime
    change_summary: str
    change_manifest: Dict[str, Any]
    rollback_version: Optional[str] = None

class GetRecentDeploymentsOutput(BaseModel):
    service_id: str
    deployments: List[DeploymentRecord]
    evidence_ids: List[str]

class RestoreSchemaMappingInput(BaseModel):
    dataset_id: str
    target_version: int

class RetryJobInput(BaseModel):
    job_id: str
    reason: str
    idempotency_key: str

class ValidateSchemaInput(BaseModel):
    job_id: str
    dataset_id: str

class ResumeDownstreamJobsInput(BaseModel):
    incident_id: str
    idempotency_key: str
