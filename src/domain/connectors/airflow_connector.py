from typing import Dict, Any, Optional
from datetime import datetime, timezone
import json

class AirflowConnector:
    """
    Parses Apache Airflow Webhook payloads and maps them to NemoGuard Alert schemas.
    """
    
    @staticmethod
    def parse_webhook(payload: Dict[str, Any], tenant_id: str = "default_tenant") -> Optional[Dict[str, Any]]:
        """
        Parses an Airflow DAG/Task failure webhook payload.
        Returns a normalized NemoGuard Alert dictionary, or None if invalid.
        """
        if "dag_id" not in payload and "task_id" not in payload:
            return None
            
        dag_id = payload.get("dag_id", "Unknown_DAG")
        task_id = payload.get("task_id", "Unknown_Task")
        run_id = payload.get("run_id", "Unknown_Run")
        state = payload.get("state", "failed").lower()
        
        severity = "high"
        if state in ["failed", "upstream_failed"]:
            severity = "high"
        elif state in ["retry", "up_for_retry"]:
            severity = "warning"
            
        title = f"Airflow Task Failed: {dag_id}.{task_id}"
        body = f"Task {task_id} in DAG {dag_id} (Run: {run_id}) transitioned to state '{state}'."
        if payload.get("log_url"):
            body += f"\nLogs: {payload.get('log_url')}"
            
        now = datetime.now(timezone.utc).isoformat()
        
        return {
            "alert_id": f"AF-{run_id}-{task_id}",
            "tenant_id": tenant_id,
            "workspace_id": "default_workspace",
            "environment_id": "production",
            "opened_ts": payload.get("execution_date", now),
            "severity": severity,
            "alert_type": "Pipeline Failure",
            "source_system": "Apache Airflow",
            "message": body,
            "affected_resource": f"airflow_task:{dag_id}.{task_id}",
            "status": "open",
            "raw_payload_json": json.dumps(payload)
        }
