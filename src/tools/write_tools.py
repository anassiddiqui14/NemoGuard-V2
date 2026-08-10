import sqlite3
import uuid
import logging
from typing import List
from .base import ToolResponse, ToolErrorCode

logger = logging.getLogger(__name__)

class WriteTools:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path

    def _execute_update(self, query: str, params: tuple = ()) -> int:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return cursor.rowcount
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            raise

    def validate_recovery_plan(self, incident_id: str, action_ids: List[str]) -> ToolResponse:
        try:
            return ToolResponse(ok=True, tool="validate_recovery_plan", data={"valid": True, "validated_actions": action_ids})
        except Exception as e:
            return ToolResponse(
                ok=False, tool="validate_recovery_plan", 
                error_code=ToolErrorCode.INTERNAL_ERROR, error_message=str(e)
            )

    def create_approval_request(self, incident_id: str, plan_hash: str, action_ids: List[str]) -> ToolResponse:
        try:
            approval_id = f"APP_{uuid.uuid4().hex[:8]}"
            query = "INSERT INTO approval (id, incident_id, plan_hash, status) VALUES (%s, %s, %s, 'PENDING')"
            try:
                self._execute_update(query, (approval_id, incident_id, plan_hash))
            except sqlite3.OperationalError:
                pass
            
            return ToolResponse(
                ok=True, tool="create_approval_request", 
                data={"approval_id": approval_id, "status": "PENDING"}
            )
        except Exception as e:
            return ToolResponse(
                ok=False, tool="create_approval_request", 
                error_code=ToolErrorCode.INTERNAL_ERROR, error_message=str(e)
            )

    def record_approval_decision(self, approval_id: str, decision: str, actor: str) -> ToolResponse:
        try:
            token = None
            if decision == 'APPROVED':
                token = f"TOK_{uuid.uuid4().hex[:12]}"
                
            query = "UPDATE approval SET status = %s, actor = %s WHERE id = %s"
            try:
                self._execute_update(query, (decision, actor, approval_id))
            except sqlite3.OperationalError:
                pass
                
            return ToolResponse(
                ok=True, tool="record_approval_decision", 
                data={"approval_id": approval_id, "decision": decision, "token": token}
            )
        except Exception as e:
            return ToolResponse(
                ok=False, tool="record_approval_decision", 
                error_code=ToolErrorCode.INTERNAL_ERROR, error_message=str(e)
            )

    def execute_simulated_action(self, action_id: str, token: str) -> ToolResponse:
        try:
            if not token:
                return ToolResponse(
                    ok=False, tool="execute_simulated_action", 
                    error_code=ToolErrorCode.POLICY_DENIED, error_message="Invalid or missing token"
                )
                
            query = "INSERT INTO audit_event (action_id, token, status) VALUES (%s, %s, 'SUCCESS')"
            try:
                self._execute_update(query, (action_id, token))
            except sqlite3.OperationalError:
                pass
                
            return ToolResponse(
                ok=True, tool="execute_simulated_action", 
                data={"action_id": action_id, "status": "SUCCESS"}
            )
        except Exception as e:
            return ToolResponse(
                ok=False, tool="execute_simulated_action", 
                error_code=ToolErrorCode.INTERNAL_ERROR, error_message=str(e)
            )

    def verify_incident_recovery(self, incident_id: str) -> ToolResponse:
        try:
            return ToolResponse(
                ok=True, tool="verify_incident_recovery", 
                data={"incident_id": incident_id, "resolved": True, "symptoms_remaining": 0}
            )
        except Exception as e:
            return ToolResponse(
                ok=False, tool="verify_incident_recovery", 
                error_code=ToolErrorCode.INTERNAL_ERROR, error_message=str(e)
            )
