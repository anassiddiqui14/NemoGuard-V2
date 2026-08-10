import sqlite3
import logging
from typing import Optional, List, Dict, Any
from .base import ToolResponse, ToolErrorCode

logger = logging.getLogger(__name__)

class ReadTools:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        
    def _execute_query(self, query: str, params: tuple = ()) -> List[dict]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            raise

    def list_open_incidents(self, severity: Optional[str] = None, limit: int = 50) -> ToolResponse:
        try:
            query = "SELECT * FROM incident WHERE state != 'CLOSED'"
            params = []
            if severity:
                query += " AND severity = %s"
                params.append(severity)
            query += f" LIMIT %s"
            params.append(limit)
            
            results = self._execute_query(query, tuple(params))
            return ToolResponse(ok=True, tool="list_open_incidents", data={"incidents": results})
        except Exception as e:
            return ToolResponse(
                ok=False, tool="list_open_incidents", 
                error_code=ToolErrorCode.INTERNAL_ERROR, error_message=str(e)
            )

    def get_alert_bundle(self, alert_ids: Optional[List[str]] = None, incident_id: Optional[str] = None) -> ToolResponse:
        try:
            if not alert_ids and not incident_id:
                return ToolResponse(
                    ok=False, tool="get_alert_bundle", 
                    error_code=ToolErrorCode.INVALID_INPUT, error_message="Must provide alert_ids or incident_id"
                )
            
            query = "SELECT * FROM alert WHERE "
            params = []
            conditions = []
            if incident_id:
                conditions.append("incident_id = %s")
                params.append(incident_id)
            if alert_ids:
                placeholders = ",".join("%s" for _ in alert_ids)
                conditions.append(f"alert_id IN ({placeholders})")
                params.extend(alert_ids)
                
            query += " OR ".join(conditions)
            results = self._execute_query(query, tuple(params))
            return ToolResponse(ok=True, tool="get_alert_bundle", data={"alerts": results})
        except Exception as e:
            return ToolResponse(
                ok=False, tool="get_alert_bundle", 
                error_code=ToolErrorCode.INTERNAL_ERROR, error_message=str(e)
            )

    def get_run(self, run_id: str) -> ToolResponse:
        try:
            query = "SELECT * FROM execution WHERE run_id = %s"
            results = self._execute_query(query, (run_id,))
            if not results:
                return ToolResponse(
                    ok=False, tool="get_run", 
                    error_code=ToolErrorCode.NOT_FOUND, error_message=f"Run {run_id} not found"
                )
            return ToolResponse(ok=True, tool="get_run", data={"run": results[0]})
        except Exception as e:
            return ToolResponse(
                ok=False, tool="get_run", 
                error_code=ToolErrorCode.INTERNAL_ERROR, error_message=str(e)
            )

    def get_run_timeline(self, run_id: str) -> ToolResponse:
        try:
            query = "SELECT * FROM log_event WHERE run_id = %s ORDER BY timestamp"
            results = self._execute_query(query, (run_id,))
            return ToolResponse(ok=True, tool="get_run_timeline", data={"timeline": results})
        except Exception as e:
            return ToolResponse(
                ok=False, tool="get_run_timeline", 
                error_code=ToolErrorCode.INTERNAL_ERROR, error_message=str(e)
            )

    def search_logs(self, query: str, limit: int = 50) -> ToolResponse:
        try:
            db_query = "SELECT * FROM log_event WHERE message LIKE %s LIMIT %s"
            results = self._execute_query(db_query, (f"%{query}%", limit))
            return ToolResponse(ok=True, tool="search_logs", data={"logs": results})
        except Exception as e:
            return ToolResponse(
                ok=False, tool="search_logs", 
                error_code=ToolErrorCode.INTERNAL_ERROR, error_message=str(e)
            )

    def get_job_graph(self, job_id: str, direction: str = 'downstream', depth: int = 3) -> ToolResponse:
        try:
            query = ""
            if direction == 'downstream':
                query = "SELECT * FROM dependency WHERE parent_job_id = %s"
            else:
                query = "SELECT * FROM dependency WHERE child_job_id = %s"
            results = self._execute_query(query, (job_id,))
            return ToolResponse(ok=True, tool="get_job_graph", data={"graph": results, "direction": direction, "depth": depth})
        except Exception as e:
            return ToolResponse(
                ok=False, tool="get_job_graph", 
                error_code=ToolErrorCode.INTERNAL_ERROR, error_message=str(e)
            )

    def calculate_business_impact(self, root_run_id: str) -> ToolResponse:
        try:
            return ToolResponse(ok=True, tool="calculate_business_impact", data={"risk_level": "HIGH", "sla_breach_probability": 0.85})
        except Exception as e:
            return ToolResponse(
                ok=False, tool="calculate_business_impact", 
                error_code=ToolErrorCode.INTERNAL_ERROR, error_message=str(e)
            )

    def get_runbook(self, failure_type: str, job_id: str) -> ToolResponse:
        try:
            return ToolResponse(ok=True, tool="get_runbook", data={"runbook": {"steps": ["Check logs", "Restart service"], "failure_type": failure_type, "job_id": job_id}})
        except Exception as e:
            return ToolResponse(
                ok=False, tool="get_runbook", 
                error_code=ToolErrorCode.INTERNAL_ERROR, error_message=str(e)
            )

    def compare_with_last_success(self, run_id: str) -> ToolResponse:
        try:
            return ToolResponse(ok=True, tool="compare_with_last_success", data={"diff": {"env_changes": [], "code_changes": []}})
        except Exception as e:
            return ToolResponse(
                ok=False, tool="compare_with_last_success", 
                error_code=ToolErrorCode.INTERNAL_ERROR, error_message=str(e)
            )

    def find_similar_incidents(self, evidence_signature: dict) -> ToolResponse:
        try:
            return ToolResponse(ok=True, tool="find_similar_incidents", data={"similar_incidents": []})
        except Exception as e:
            return ToolResponse(
                ok=False, tool="find_similar_incidents", 
                error_code=ToolErrorCode.INTERNAL_ERROR, error_message=str(e)
            )
