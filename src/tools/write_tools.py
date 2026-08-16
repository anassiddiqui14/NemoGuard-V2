import os
import sqlite3
import uuid
import logging
from typing import List, Optional
from .base import ToolResponse, ToolErrorCode

logger = logging.getLogger(__name__)

# When set, execute_simulated_action / verify_incident_recovery call into the
# LocalStack lab (localstack_lab/remediate.py) to perform and verify REAL
# remediation actions (real boto3 Lambda invoke, real Postgres row checks)
# instead of the default no-op simulated behavior. Off by default so normal
# NemoGuard operation (against real cloud infra, or with the lab not
# running) is completely unaffected.
LOCALSTACK_LAB_ENABLED = os.environ.get("NEMOGUARD_LOCALSTACK_LAB", "0") == "1"

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

    def execute_simulated_action(self, action_id: str, token: str, run_id: Optional[str] = None,
                                  job: str = "ingest_job", orders: Optional[List[dict]] = None) -> ToolResponse:
        """
        job: which real LocalStack-lab job to remediate:
            "ingest_job"     -> rerun_ingest_job (schema-drift style S3->Postgres Lambda)
            "order_events"   -> idempotent_rerun_order_events_job (staleness-check ->
                                 cleanup -> rerun -> verify for the write-job scenario;
                                 requires `orders` to be the full/corrected batch)
        """
        try:
            if not token:
                return ToolResponse(
                    ok=False, tool="execute_simulated_action", 
                    error_code=ToolErrorCode.POLICY_DENIED, error_message="Invalid or missing token"
                )

            lab_result = None
            if LOCALSTACK_LAB_ENABLED and run_id:
                # Perform a REAL remediation action against the LocalStack
                # lab instead of a no-op: re-invoke the real Lambda job with
                # a corrected payload for this run_id, so "execute the
                # recovery plan" actually does something verifiable.
                try:
                    if job == "order_events":
                        from localstack_lab.remediate import idempotent_rerun_order_events_job
                        lab_result = idempotent_rerun_order_events_job(run_id, orders or [])
                    else:
                        from localstack_lab.remediate import rerun_ingest_job
                        lab_result = rerun_ingest_job(run_id)
                except Exception as lab_e:
                    logger.error(f"LocalStack lab remediation failed: {lab_e}")
                    lab_result = {"success": False, "error": str(lab_e)}

            query = "INSERT INTO audit_event (action_id, token, status) VALUES (%s, %s, 'SUCCESS')"
            try:
                self._execute_update(query, (action_id, token))
            except sqlite3.OperationalError:
                pass

            data = {"action_id": action_id, "status": "SUCCESS"}
            if lab_result is not None:
                data["localstack_lab_result"] = lab_result

            return ToolResponse(
                ok=True, tool="execute_simulated_action", 
                data=data
            )
        except Exception as e:
            return ToolResponse(
                ok=False, tool="execute_simulated_action", 
                error_code=ToolErrorCode.INTERNAL_ERROR, error_message=str(e)
            )

    def verify_incident_recovery(self, incident_id: str, run_id: Optional[str] = None) -> ToolResponse:
        try:
            if LOCALSTACK_LAB_ENABLED and run_id:
                # REAL verification: check the actual execution row + real
                # CloudWatch alarm state written by the LocalStack lab,
                # instead of hardcoding resolved=True.
                try:
                    from localstack_lab.remediate import check_job_succeeded, check_alarm_state
                    job_check = check_job_succeeded(run_id)
                    alarm_check = check_alarm_state()
                    resolved = bool(job_check.get("resolved")) and bool(alarm_check.get("resolved"))
                    return ToolResponse(
                        ok=True, tool="verify_incident_recovery",
                        data={
                            "incident_id": incident_id,
                            "resolved": resolved,
                            "symptoms_remaining": 0 if resolved else 1,
                            "job_check": job_check,
                            "alarm_check": alarm_check,
                        }
                    )
                except Exception as lab_e:
                    logger.error(f"LocalStack lab verification failed: {lab_e}")
                    return ToolResponse(
                        ok=False, tool="verify_incident_recovery",
                        error_code=ToolErrorCode.INTERNAL_ERROR, error_message=str(lab_e)
                    )

            return ToolResponse(
                ok=True, tool="verify_incident_recovery", 
                data={"incident_id": incident_id, "resolved": True, "symptoms_remaining": 0}
            )
        except Exception as e:
            return ToolResponse(
                ok=False, tool="verify_incident_recovery", 
                error_code=ToolErrorCode.INTERNAL_ERROR, error_message=str(e)
            )
