DROP TABLE IF EXISTS incident_alert;
DROP TABLE IF EXISTS incident_evidence;
DROP TABLE IF EXISTS approval;
DROP TABLE IF EXISTS audit_event;
DROP TABLE IF EXISTS incident;
DROP TABLE IF EXISTS action_plan;

CREATE TABLE IF NOT EXISTS incident (

    tenant_id VARCHAR DEFAULT 'default_tenant',
    workspace_id VARCHAR,
    environment_id VARCHAR,
    incident_id VARCHAR PRIMARY KEY,
    title VARCHAR NOT NULL,
    summary VARCHAR,
    status VARCHAR NOT NULL,
    severity VARCHAR NOT NULL,
    primary_job_id VARCHAR,
    primary_run_id VARCHAR,
    owner_team VARCHAR,
    detected_at VARCHAR NOT NULL,
    created_at VARCHAR NOT NULL,
    updated_at VARCHAR NOT NULL,
    resolved_at VARCHAR,
    correlation_confidence REAL,
    rca_confidence REAL,
    next_sla_breach_at VARCHAR,
    actual_root_cause VARCHAR,
    resolution_summary VARCHAR,
    version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(primary_job_id) REFERENCES job(job_id),
    FOREIGN KEY(primary_run_id) REFERENCES execution(run_id)
);

CREATE TABLE IF NOT EXISTS incident_alert (
    incident_id VARCHAR NOT NULL,
    alert_id VARCHAR NOT NULL,
    relation_type VARCHAR NOT NULL DEFAULT 'CORRELATED',
    correlation_score REAL NOT NULL,
    correlation_reasons_json VARCHAR NOT NULL,
    added_at VARCHAR NOT NULL,
    PRIMARY KEY(incident_id, alert_id),
    FOREIGN KEY(incident_id) REFERENCES incident(incident_id),
    FOREIGN KEY(alert_id) REFERENCES alert(alert_id)
);

CREATE TABLE IF NOT EXISTS agent_run (

    tenant_id VARCHAR DEFAULT 'default_tenant',
    workspace_id VARCHAR,
    environment_id VARCHAR,
    agent_run_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    agent_name VARCHAR NOT NULL,
    parent_agent_run_id VARCHAR,
    objective VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    model_provider VARCHAR,
    model_name VARCHAR,
    started_at VARCHAR,
    completed_at VARCHAR,
    token_input INTEGER,
    token_output INTEGER,
    latency_ms INTEGER,
    error_message VARCHAR,
    FOREIGN KEY(incident_id) REFERENCES incident(incident_id),
    FOREIGN KEY(parent_agent_run_id) REFERENCES agent_run(agent_run_id)
);

CREATE TABLE IF NOT EXISTS agent_step (

    tenant_id VARCHAR DEFAULT 'default_tenant',
    workspace_id VARCHAR,
    environment_id VARCHAR,
    agent_step_id VARCHAR PRIMARY KEY,
    agent_run_id VARCHAR NOT NULL,
    sequence_no INTEGER NOT NULL,
    step_type VARCHAR NOT NULL,
    summary VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    input_json VARCHAR,
    output_json VARCHAR,
    started_at VARCHAR NOT NULL,
    completed_at VARCHAR,
    FOREIGN KEY(agent_run_id) REFERENCES agent_run(agent_run_id),
    UNIQUE(agent_run_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS tool_call (

    tenant_id VARCHAR DEFAULT 'default_tenant',
    workspace_id VARCHAR,
    environment_id VARCHAR,
    tool_call_id VARCHAR PRIMARY KEY,
    agent_run_id VARCHAR NOT NULL,
    agent_step_id VARCHAR,
    tool_name VARCHAR NOT NULL,
    risk_level VARCHAR NOT NULL,
    arguments_json VARCHAR NOT NULL,
    result_json VARCHAR,
    status VARCHAR NOT NULL,
    started_at VARCHAR NOT NULL,
    completed_at VARCHAR,
    duration_ms INTEGER,
    error_message VARCHAR,
    FOREIGN KEY(agent_run_id) REFERENCES agent_run(agent_run_id),
    FOREIGN KEY(agent_step_id) REFERENCES agent_step(agent_step_id)
);

CREATE TABLE IF NOT EXISTS evidence (

    tenant_id VARCHAR DEFAULT 'default_tenant',
    workspace_id VARCHAR,
    environment_id VARCHAR,
    evidence_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    tool_call_id VARCHAR,
    evidence_type VARCHAR NOT NULL,
    source_system VARCHAR NOT NULL,
    source_record_id VARCHAR,
    title VARCHAR NOT NULL,
    excerpt VARCHAR NOT NULL,
    occurred_at VARCHAR,
    collected_at VARCHAR NOT NULL,
    reliability REAL NOT NULL DEFAULT 1.0,
    metadata_json VARCHAR,
    FOREIGN KEY(incident_id) REFERENCES incident(incident_id),
    FOREIGN KEY(tool_call_id) REFERENCES tool_call(tool_call_id)
);

CREATE TABLE IF NOT EXISTS hypothesis (

    tenant_id VARCHAR DEFAULT 'default_tenant',
    workspace_id VARCHAR,
    environment_id VARCHAR,
    hypothesis_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    agent_run_id VARCHAR NOT NULL,
    rank_no INTEGER NOT NULL,
    statement VARCHAR NOT NULL,
    cause_type VARCHAR,
    confidence REAL NOT NULL,
    status VARCHAR NOT NULL,
    supporting_evidence_json VARCHAR NOT NULL,
    contradicting_evidence_json VARCHAR NOT NULL,
    missing_evidence_json VARCHAR NOT NULL,
    created_at VARCHAR NOT NULL,
    FOREIGN KEY(incident_id) REFERENCES incident(incident_id),
    FOREIGN KEY(agent_run_id) REFERENCES agent_run(agent_run_id)
);

CREATE TABLE IF NOT EXISTS data_asset (
    asset_id VARCHAR PRIMARY KEY,
    asset_type VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    description VARCHAR,
    owner_team VARCHAR,
    criticality VARCHAR,
    freshness_sla_minutes INTEGER,
    business_process VARCHAR,
    estimated_user_count INTEGER,
    impact_band VARCHAR,
    metadata_json VARCHAR
);

CREATE TABLE IF NOT EXISTS asset_dependency (
    parent_asset_id VARCHAR NOT NULL,
    child_asset_id VARCHAR NOT NULL,
    relationship_type VARCHAR NOT NULL,
    PRIMARY KEY(parent_asset_id, child_asset_id, relationship_type),
    FOREIGN KEY(parent_asset_id) REFERENCES data_asset(asset_id),
    FOREIGN KEY(child_asset_id) REFERENCES data_asset(asset_id)
);

CREATE TABLE IF NOT EXISTS incident_impact (
    incident_id VARCHAR NOT NULL,
    asset_id VARCHAR NOT NULL,
    impact_type VARCHAR NOT NULL,
    impact_status VARCHAR NOT NULL,
    reason VARCHAR NOT NULL,
    expected_breach_at VARCHAR,
    impact_score REAL NOT NULL,
    evidence_ids_json VARCHAR NOT NULL,
    PRIMARY KEY(incident_id, asset_id),
    FOREIGN KEY(incident_id) REFERENCES incident(incident_id),
    FOREIGN KEY(asset_id) REFERENCES data_asset(asset_id)
);

CREATE TABLE IF NOT EXISTS deployment (
    deployment_id VARCHAR PRIMARY KEY,
    service_id VARCHAR NOT NULL,
    version VARCHAR NOT NULL,
    environment VARCHAR NOT NULL,
    deployed_at VARCHAR NOT NULL,
    deployed_by VARCHAR,
    change_summary VARCHAR NOT NULL,
    change_manifest_json VARCHAR NOT NULL,
    rollback_version VARCHAR,
    status VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_version (
    schema_version_id VARCHAR PRIMARY KEY,
    dataset_id VARCHAR NOT NULL,
    version_no INTEGER NOT NULL,
    effective_at VARCHAR NOT NULL,
    columns_json VARCHAR NOT NULL,
    compatibility_status VARCHAR,
    change_summary VARCHAR,
    source_deployment_id VARCHAR,
    FOREIGN KEY(source_deployment_id) REFERENCES deployment(deployment_id),
    UNIQUE(dataset_id, version_no)
);

CREATE TABLE IF NOT EXISTS runbook (

    tenant_id VARCHAR DEFAULT 'default_tenant',
    workspace_id VARCHAR,
    environment_id VARCHAR,
    runbook_id VARCHAR PRIMARY KEY,
    title VARCHAR NOT NULL,
    incident_type VARCHAR NOT NULL,
    version INTEGER NOT NULL,
    status VARCHAR NOT NULL,
    owner_team VARCHAR NOT NULL,
    approval_policy VARCHAR NOT NULL,
    prerequisites_json VARCHAR NOT NULL,
    verification_json VARCHAR NOT NULL,
    rollback_json VARCHAR NOT NULL,
    created_at VARCHAR NOT NULL,
    updated_at VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS runbook_step (
    runbook_id VARCHAR NOT NULL,
    step_no INTEGER NOT NULL,
    title VARCHAR NOT NULL,
    instruction VARCHAR NOT NULL,
    tool_name VARCHAR,
    risk_level VARCHAR NOT NULL,
    requires_approval INTEGER NOT NULL,
    parameters_template_json VARCHAR,
    PRIMARY KEY(runbook_id, step_no),
    FOREIGN KEY(runbook_id) REFERENCES runbook(runbook_id)
);

CREATE TABLE IF NOT EXISTS action_plan (

    tenant_id VARCHAR DEFAULT 'default_tenant',
    workspace_id VARCHAR,
    environment_id VARCHAR,
    action_plan_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    agent_run_id VARCHAR NOT NULL,
    runbook_id VARCHAR,
    plan_version INTEGER NOT NULL,
    status VARCHAR NOT NULL,
    overall_risk VARCHAR NOT NULL,
    rationale VARCHAR NOT NULL,
    expected_outcome VARCHAR NOT NULL,
    rollback_summary VARCHAR NOT NULL,
    created_at VARCHAR NOT NULL,
    FOREIGN KEY(incident_id) REFERENCES incident(incident_id),
    FOREIGN KEY(agent_run_id) REFERENCES agent_run(agent_run_id),
    FOREIGN KEY(runbook_id) REFERENCES runbook(runbook_id)
);

CREATE TABLE IF NOT EXISTS action_step (

    tenant_id VARCHAR DEFAULT 'default_tenant',
    workspace_id VARCHAR,
    environment_id VARCHAR,
    action_step_id VARCHAR PRIMARY KEY,
    action_plan_id VARCHAR NOT NULL,
    sequence_no INTEGER NOT NULL,
    action_type VARCHAR NOT NULL,
    tool_name VARCHAR NOT NULL,
    risk_level VARCHAR NOT NULL,
    requires_approval INTEGER NOT NULL,
    parameters_json VARCHAR NOT NULL,
    preconditions_json VARCHAR NOT NULL,
    expected_postconditions_json VARCHAR NOT NULL,
    rollback_tool_name VARCHAR,
    rollback_parameters_json VARCHAR,
    status VARCHAR NOT NULL,
    FOREIGN KEY(action_plan_id) REFERENCES action_plan(action_plan_id),
    UNIQUE(action_plan_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS approval (

    tenant_id VARCHAR DEFAULT 'default_tenant',
    workspace_id VARCHAR,
    environment_id VARCHAR,
    approval_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    action_plan_id VARCHAR NOT NULL,
    requested_at VARCHAR NOT NULL,
    expires_at VARCHAR NOT NULL,
    decision VARCHAR NOT NULL,
    decided_at VARCHAR,
    approver_id VARCHAR,
    approver_role VARCHAR,
    comment VARCHAR,
    plan_hash VARCHAR NOT NULL,
    FOREIGN KEY(incident_id) REFERENCES incident(incident_id),
    FOREIGN KEY(action_plan_id) REFERENCES action_plan(action_plan_id)
);

CREATE TABLE IF NOT EXISTS action_execution (
    action_execution_id VARCHAR PRIMARY KEY,
    action_step_id VARCHAR NOT NULL,
    approval_id VARCHAR,
    idempotency_key VARCHAR NOT NULL UNIQUE,
    status VARCHAR NOT NULL,
    started_at VARCHAR,
    completed_at VARCHAR,
    before_state_json VARCHAR,
    after_state_json VARCHAR,
    result_json VARCHAR,
    error_message VARCHAR,
    FOREIGN KEY(action_step_id) REFERENCES action_step(action_step_id),
    FOREIGN KEY(approval_id) REFERENCES approval(approval_id)
);

CREATE TABLE IF NOT EXISTS verification_result (
    verification_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    action_plan_id VARCHAR NOT NULL,
    check_name VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    expected_json VARCHAR NOT NULL,
    actual_json VARCHAR NOT NULL,
    evidence_ids_json VARCHAR NOT NULL,
    checked_at VARCHAR NOT NULL,
    FOREIGN KEY(incident_id) REFERENCES incident(incident_id),
    FOREIGN KEY(action_plan_id) REFERENCES action_plan(action_plan_id)
);

CREATE TABLE IF NOT EXISTS feedback (
    feedback_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    submitted_at VARCHAR NOT NULL,
    submitted_by VARCHAR NOT NULL,
    actual_root_cause VARCHAR,
    recommendation_correct INTEGER,
    impact_correct INTEGER,
    runbook_helpful INTEGER,
    action_successful INTEGER,
    notes VARCHAR,
    FOREIGN KEY(incident_id) REFERENCES incident(incident_id)
);

CREATE TABLE IF NOT EXISTS audit_event (

    tenant_id VARCHAR DEFAULT 'default_tenant',
    workspace_id VARCHAR,
    environment_id VARCHAR,
    audit_event_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR,
    actor_type VARCHAR NOT NULL,
    actor_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    event_summary VARCHAR NOT NULL,
    details_json VARCHAR,
    created_at VARCHAR NOT NULL,
    FOREIGN KEY(incident_id) REFERENCES incident(incident_id)
);

-- INDEXES
CREATE INDEX IF NOT EXISTS idx_alert_status_time ON alert(status, opened_ts);
CREATE INDEX IF NOT EXISTS idx_incident_status_updated ON incident(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_incident_alert_alert ON incident_alert(alert_id);
CREATE INDEX IF NOT EXISTS idx_log_event_run_time ON log_event(run_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_tool_call_agent ON tool_call(agent_run_id, started_at);
CREATE INDEX IF NOT EXISTS idx_evidence_incident ON evidence(incident_id, evidence_type);
CREATE INDEX IF NOT EXISTS idx_deployment_service_time ON deployment(service_id, deployed_at DESC);
CREATE INDEX IF NOT EXISTS idx_schema_dataset_time ON schema_version(dataset_id, effective_at DESC);
