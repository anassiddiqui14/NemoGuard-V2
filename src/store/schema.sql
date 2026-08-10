-- Seed/reference data
CREATE TABLE IF NOT EXISTS job (

    tenant_id VARCHAR DEFAULT 'default_tenant',
    workspace_id VARCHAR,
    environment_id VARCHAR,
  job_id VARCHAR PRIMARY KEY,
  job_name VARCHAR NOT NULL,
  platform VARCHAR NOT NULL,
  domain VARCHAR NOT NULL,
  stage VARCHAR NOT NULL,
  schedule VARCHAR NOT NULL,
  criticality INTEGER NOT NULL,
  default_duration_sec INTEGER NOT NULL,
  owner_team VARCHAR NOT NULL,
  retry_policy VARCHAR NOT NULL,
  active BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS dependency (
  edge_id VARCHAR PRIMARY KEY,
  parent_job_id VARCHAR NOT NULL REFERENCES job(job_id),
  child_job_id VARCHAR NOT NULL REFERENCES job(job_id),
  dependency_type VARCHAR NOT NULL,
  max_lag_min INTEGER NOT NULL,
  required BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS business_asset (
  asset_id VARCHAR PRIMARY KEY,
  asset_name VARCHAR NOT NULL,
  asset_type VARCHAR NOT NULL,
  owner VARCHAR NOT NULL,
  sla_minutes INTEGER NOT NULL,
  criticality INTEGER NOT NULL,
  communication_template VARCHAR
);

CREATE TABLE IF NOT EXISTS asset_dependency (
  asset_id VARCHAR NOT NULL REFERENCES business_asset(asset_id),
  job_id VARCHAR NOT NULL REFERENCES job(job_id),
  PRIMARY KEY (asset_id, job_id)
);

-- Runtime/generated data
CREATE TABLE IF NOT EXISTS execution (

    tenant_id VARCHAR DEFAULT 'default_tenant',
    workspace_id VARCHAR,
    environment_id VARCHAR,
  run_id VARCHAR PRIMARY KEY,
  job_id VARCHAR NOT NULL REFERENCES job(job_id),
  scheduled_ts VARCHAR NOT NULL,
  start_ts VARCHAR NOT NULL,
  end_ts VARCHAR,
  status VARCHAR NOT NULL CHECK(status IN ('queued','running','succeeded','failed','blocked','skipped')),
  attempt INTEGER NOT NULL DEFAULT 1,
  records_in INTEGER,
  records_out INTEGER,
  schema_version VARCHAR,
  incident_id VARCHAR
);

CREATE TABLE IF NOT EXISTS log_event (

    tenant_id VARCHAR DEFAULT 'default_tenant',
    workspace_id VARCHAR,
    environment_id VARCHAR,
  log_id VARCHAR PRIMARY KEY,
  run_id VARCHAR NOT NULL REFERENCES execution(run_id),
  timestamp VARCHAR NOT NULL,
  level VARCHAR NOT NULL CHECK(level IN ('DEBUG','INFO','WARN','ERROR')),
  component VARCHAR NOT NULL,
  error_code VARCHAR,
  message VARCHAR NOT NULL,
  attributes_json VARCHAR
);

CREATE TABLE IF NOT EXISTS alert (

    tenant_id VARCHAR DEFAULT 'default_tenant',
    workspace_id VARCHAR,
    environment_id VARCHAR,
  alert_id VARCHAR PRIMARY KEY,
  run_id VARCHAR,
  opened_ts VARCHAR NOT NULL,
  severity VARCHAR NOT NULL CHECK(severity IN ('info','warning','high','critical')),
  alert_type VARCHAR NOT NULL,
  source_system VARCHAR NOT NULL DEFAULT 'Pipeline Monitor',
  message VARCHAR NOT NULL,
  status VARCHAR NOT NULL DEFAULT 'open' CHECK(status IN ('open','acknowledged','resolved'))
);

-- Incident management (runtime)
CREATE TABLE IF NOT EXISTS incident (

    tenant_id VARCHAR DEFAULT 'default_tenant',
    workspace_id VARCHAR,
    environment_id VARCHAR,
  incident_id VARCHAR PRIMARY KEY,
  state VARCHAR NOT NULL DEFAULT 'NEW',
  opened_ts VARCHAR NOT NULL,
  severity VARCHAR NOT NULL DEFAULT 'high',
  primary_hypothesis_json VARCHAR,
  impact_json VARCHAR,
  active_plan_hash VARCHAR,
  updated_ts VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS incident_alert (
  incident_id VARCHAR NOT NULL REFERENCES incident(incident_id),
  alert_id VARCHAR NOT NULL REFERENCES alert(alert_id),
  PRIMARY KEY (incident_id, alert_id)
);

CREATE TABLE IF NOT EXISTS incident_evidence (
  incident_id VARCHAR NOT NULL,
  evidence_id VARCHAR NOT NULL,
  evidence_type VARCHAR NOT NULL,
  added_by VARCHAR NOT NULL DEFAULT 'agent',
  added_ts VARCHAR NOT NULL,
  PRIMARY KEY (incident_id, evidence_id)
);

CREATE TABLE IF NOT EXISTS approval (

    tenant_id VARCHAR DEFAULT 'default_tenant',
    workspace_id VARCHAR,
    environment_id VARCHAR,
  approval_id VARCHAR PRIMARY KEY,
  incident_id VARCHAR NOT NULL,
  plan_hash VARCHAR NOT NULL,
  status VARCHAR NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
  requested_ts VARCHAR NOT NULL,
  decided_ts VARCHAR,
  decided_by VARCHAR,
  decision_comment VARCHAR,
  token_json VARCHAR
);

CREATE TABLE IF NOT EXISTS audit_event (

    tenant_id VARCHAR DEFAULT 'default_tenant',
    workspace_id VARCHAR,
    environment_id VARCHAR,
  audit_id VARCHAR PRIMARY KEY,
  incident_id VARCHAR,
  timestamp VARCHAR NOT NULL,
  actor_type VARCHAR NOT NULL,
  actor_id VARCHAR NOT NULL,
  event_type VARCHAR NOT NULL,
  payload_json VARCHAR NOT NULL
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_execution_job ON execution(job_id);
CREATE INDEX IF NOT EXISTS idx_execution_status ON execution(status);
CREATE INDEX IF NOT EXISTS idx_execution_scheduled ON execution(scheduled_ts);
CREATE INDEX IF NOT EXISTS idx_log_run ON log_event(run_id);
CREATE INDEX IF NOT EXISTS idx_log_level ON log_event(level);
CREATE INDEX IF NOT EXISTS idx_log_error_code ON log_event(error_code);
CREATE INDEX IF NOT EXISTS idx_alert_status ON alert(status);
CREATE INDEX IF NOT EXISTS idx_alert_run ON alert(run_id);
CREATE INDEX IF NOT EXISTS idx_audit_incident ON audit_event(incident_id);
