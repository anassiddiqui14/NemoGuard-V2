import sqlite3
import json
from datetime import datetime, timedelta

def inject_scenario(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Insert Deployment
    deployment_id = "DEP-442"
    cursor.execute("""
        INSERT OR IGNORE INTO deployment (
            deployment_id, service_id, version, environment, deployed_at, 
            deployed_by, change_summary, change_manifest_json, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        deployment_id, "SERVICE-CUSTOMER-PIPELINE", "v2.1.0", "PROD", 
        "2026-08-04T09:44:08Z", "auto-deploy", "Customer profile schema mapping updated: loyalty_id -> member_id",
        json.dumps({"renamed_columns": {"loyalty_id": "member_id"}}), "SUCCESS"
    ))

    # 2. Insert Schema Versions
    dataset_id = "DATASET-CUSTOMER-PROFILE"
    cursor.execute("""
        INSERT OR IGNORE INTO schema_version (
            schema_version_id, dataset_id, version_no, effective_at, columns_json, 
            compatibility_status, change_summary, source_deployment_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "SCHEMA-118", dataset_id, 118, "2026-08-01T00:00:00Z",
        json.dumps([{"name": "loyalty_id", "type": "STRING", "nullable": False}]),
        "COMPATIBLE", "Initial schema", None
    ))

    cursor.execute("""
        INSERT OR IGNORE INTO schema_version (
            schema_version_id, dataset_id, version_no, effective_at, columns_json, 
            compatibility_status, change_summary, source_deployment_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "SCHEMA-119", dataset_id, 119, "2026-08-04T09:44:08Z",
        json.dumps([{"name": "member_id", "type": "STRING", "nullable": False}]),
        "INCOMPATIBLE", "Renamed loyalty_id to member_id", deployment_id
    ))

    # 3. Create a failed execution for the scenario
    run_id = "RUN-9821"
    job_id = "JOB-CUST-INGEST-01"
    start_ts = "2026-08-04T10:02:00Z"
    cursor.execute("""
        INSERT OR IGNORE INTO execution (
            run_id, job_id, scheduled_ts, start_ts, end_ts, status, attempt
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (run_id, job_id, start_ts, start_ts, "2026-08-04T10:02:17Z", "failed", 1))

    # 4. Insert logs
    cursor.execute("""
        INSERT OR IGNORE INTO log_event (
            log_id, run_id, timestamp, level, component, error_code, message
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        "LOG-8812", run_id, "2026-08-04T10:02:17Z", "ERROR", "SchemaValidator", 
        "SCHEMA_COLUMN_MISSING", "SCHEMA_COLUMN_MISSING: expected column loyalty_id; available columns include member_id"
    ))

    # 5. Insert Alerts
    alert_id = "ALT-101"
    cursor.execute("""
        INSERT OR IGNORE INTO alert (
            alert_id, run_id, opened_ts, severity, alert_type, source_system, message, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        alert_id, run_id, "2026-08-04T10:03:00Z", "high", "JOB_FAILURE", "CloudWatch", 
        "Customer profile ingestion failed", "open"
    ))

    conn.commit()
    conn.close()
    print("Scenario SCN-SCHEMA-DEPLOY-001 injected successfully.")

if __name__ == "__main__":
    inject_scenario("data/generated/pipeline.db")
