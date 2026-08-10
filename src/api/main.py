from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Depends
from fastapi.responses import StreamingResponse, JSONResponse
import asyncio
from pydantic import BaseModel
import random
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import os
import json
import uuid

from src.store.postgres_database import PostgresDatabase
from src.domain.enums import IncidentState
from src.domain.orchestrator import IncidentOrchestrator
from src.domain.correlator import CorrelatorEngine
from src.domain.models import Incident, Alert
from src.utils.telemetry import setup_telemetry
from src.api.auth import get_current_user, require_role, User, get_mock_token

from temporalio.client import Client
from src.domain.workflows.incident_workflow import IncidentLifecycleWorkflow

app = FastAPI(title="NemoGuard - Pipeline Incident Commander", version="2.0.0")
setup_telemetry("nemoguard_api")

temporal_client = None

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"Global error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": str(exc), "path": request.url.path}
    )

@app.get("/api/v2/auth/mock-login")
def mock_login(role: str = "commander"):
    if os.environ.get("ENV", "production").lower() not in ("development", "dev", "local"):
        raise HTTPException(status_code=404, detail="Not found")
    return {"access_token": get_mock_token(role), "token_type": "bearer"}

@app.on_event("startup")
async def startup_event():
    global temporal_client
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    try:
        # Check if tables exist
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename = 'incident'")
            if not cursor.fetchone():
                print("Initializing database schema...")
                db.init_schema()
    except Exception as e:
        print(f"Failed to initialize database: {e}")
        
    try:
        temporal_url = os.getenv("TEMPORAL_URL", "localhost:7233")
        temporal_client = await Client.connect(temporal_url)
        print(f"Connected to Temporal server at {temporal_url}")
    except Exception as e:
        print(f"Failed to connect to Temporal: {e}")

# --- 12.1 Overview endpoints ---

@app.get("/api/v2/status")
def get_status():
    return {
        "environment": "development",
        "inference_provider": "nvidia_nim",
        "orchestrator": "healthy",
        "policy_engine": "active",
        "database": "healthy",
        "last_checked_at": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/v2/overview")
def get_overview():
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    try:
        with db.get_connection() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM incident WHERE status != 'RESOLVED'")
            open_incidents = cur.fetchone()[0]
            cur = conn.execute("SELECT COUNT(*) FROM incident WHERE status != 'RESOLVED' AND severity = 'SEV-1'")
            critical = cur.fetchone()[0]
            cur = conn.execute("SELECT COUNT(*) FROM incident WHERE status != 'RESOLVED' AND severity = 'SEV-2'")
            high = cur.fetchone()[0]
            cur = conn.execute("SELECT COUNT(*) FROM alert WHERE status = 'acknowledged'")
            correlated = cur.fetchone()[0]
            
            return {
                "open_incidents": open_incidents,
                "critical_incidents": critical,
                "high_incidents": high,
                "alerts_correlated_today": correlated,
                "alerts_suppressed_today": 0,
                "jobs_currently_affected": 8 if open_incidents > 0 else 0,
                "data_products_at_risk": 3 if open_incidents > 0 else 0
            }
    except Exception:
        return {}

@app.get("/api/v2/incidents")
def list_incidents(state: str = "open"):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        if state == "open":
            cursor = conn.execute("SELECT incident_id, title, status, severity, detected_at, next_sla_breach_at, owner_team, primary_job_id, summary FROM incident WHERE status != 'RESOLVED' ORDER BY detected_at DESC")
        else:
            cursor = conn.execute("SELECT incident_id, title, status, severity, detected_at, next_sla_breach_at, owner_team, primary_job_id, summary FROM incident ORDER BY detected_at DESC")
            
        cols = [col[0] for col in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

# --- 12.2 Incident detail endpoints ---

@app.get("/api/v2/incidents/{incident_id}")
def get_incident(incident_id: str):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM incident WHERE incident_id = %s", (incident_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Incident not found")
        cols = [col[0] for col in cursor.description]
        return dict(zip(cols, row))

@app.get("/api/v2/incidents/{incident_id}/summary")
def get_incident_summary(incident_id: str):
    # For now, just return the incident details
    return get_incident(incident_id)

@app.get("/api/v2/incidents/{incident_id}/hypotheses")
def get_hypotheses(incident_id: str):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM hypothesis WHERE incident_id = %s ORDER BY confidence DESC", (incident_id,))
        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
        for r in rows:
            r['supporting_evidence_ids'] = json.loads(r['supporting_evidence_json'])
            r['contradicting_evidence_ids'] = json.loads(r['contradicting_evidence_json'])
        return rows

@app.get("/api/v2/incidents/{incident_id}/evidence")
def get_evidence(incident_id: str):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM evidence WHERE incident_id = %s ORDER BY collected_at ASC", (incident_id,))
        cols = [col[0] for col in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

@app.get("/api/v2/incidents/{incident_id}/impact")
def get_impact(incident_id: str):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        cursor = conn.execute("""
            SELECT i.*, d.name as asset_name, d.freshness_sla_minutes 
            FROM incident_impact i 
            LEFT JOIN data_asset d ON i.asset_id = d.asset_id 
            WHERE i.incident_id = %s
        """, (incident_id,))
        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
        for r in rows:
            r['evidence_ids'] = json.loads(r['evidence_ids_json'])
        return rows

@app.get("/api/v2/incidents/{incident_id}/plans")
def get_plans(incident_id: str):
    from src.domain.plan_hash import compute_plan_hash
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM action_plan WHERE incident_id = %s ORDER BY created_at DESC", (incident_id,))
        cols = [col[0] for col in cursor.description]
        plans = [dict(zip(cols, row)) for row in cursor.fetchall()]
        
        for plan in plans:
            cursor = conn.execute("SELECT * FROM action_step WHERE action_plan_id = %s ORDER BY sequence_no ASC", (plan['action_plan_id'],))
            step_cols = [col[0] for col in cursor.description]
            plan['steps'] = [dict(zip(step_cols, row)) for row in cursor.fetchall()]
            # Compute the real content hash so the frontend can send it back unchanged on /approve.
            plan['plan_hash'] = compute_plan_hash(plan, plan['steps'])
        return plans

@app.get("/api/v2/incidents/{incident_id}/events")
def get_events(incident_id: str):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM audit_event WHERE incident_id = %s ORDER BY created_at ASC", (incident_id,))
        cols = [col[0] for col in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

@app.get("/api/v2/incidents/{incident_id}/alerts")
def get_incident_alerts(incident_id: str):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        cursor = conn.execute("""
            SELECT a.* FROM alert a
            JOIN incident_alert ia ON a.alert_id = ia.alert_id
            WHERE ia.incident_id = %s
        """, (incident_id,))
        cols = [col[0] for col in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

@app.get("/api/v2/alerts")
def get_all_alerts():
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM alert ORDER BY opened_ts DESC")
        cols = [col[0] for col in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

# --- 12.3 Context Endpoints (for NemoClaw Agents) ---

@app.get("/api/v2/context/alerts/{incident_id}")
def get_incident_alerts_context(incident_id: str):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        cursor = conn.execute("""
            SELECT a.alert_id, a.alert_type, a.source_system, a.message, a.opened_ts 
            FROM alert a
            JOIN incident_alert ia ON a.alert_id = ia.alert_id
            WHERE ia.incident_id = %s
        """, (incident_id,))
        cols = [col[0] for col in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

@app.get("/api/v2/context/logs/{incident_id}")
def get_incident_logs_context(incident_id: str):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT primary_run_id FROM incident WHERE incident_id = %s", (incident_id,))
        run_id_row = cursor.fetchone()
        if run_id_row and run_id_row[0]:
            cursor = conn.execute("SELECT message FROM log_event WHERE run_id = %s", (run_id_row[0],))
            return [row[0] for row in cursor.fetchall()]
        return []

@app.get("/api/v2/context/cmdb")
def get_cmdb_context():
    import json
    with open("data/mock_dimensions/cmdb.json", "r") as f:
        return json.load(f)

@app.get("/api/v2/context/runbooks")
def get_runbooks_context():
    import json
    with open("data/mock_dimensions/runbooks.json", "r") as f:
        return json.load(f)

# --- 12.4 Workflow endpoints ---

@app.post("/api/v2/ingest/webhook")
async def ingest_webhook(payload: dict):
    """
    Generic webhook endpoint for Datadog, PagerDuty, or Email-to-Webhook parsing.
    Passes the payload to the WatcherAgent to determine if it's a valid alert.
    """
    orchestrator = IncidentOrchestrator()
    result = await orchestrator.process_webhook(payload)
    
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))
        
    if result.get("status") == "ingested_and_incident_created":
        incident_id = result.get("incident_id")
        global temporal_client
        if temporal_client:
            from src.domain.workflows.incident_workflow import IncidentLifecycleWorkflow
            await temporal_client.start_workflow(
                IncidentLifecycleWorkflow.run,
                incident_id,
                id=f"incident-{incident_id}",
                task_queue="incident-task-queue",
            )
        
    return result

@app.post("/api/v2/incidents/{incident_id}/triage")
async def triage_incident(incident_id: str, current_user: User = Depends(get_current_user)):
    """
    Triage can take a long time, so we schedule it in Temporal.
    """
    global temporal_client
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE incident SET status = %s WHERE incident_id = %s",
            (IncidentState.INVESTIGATING.value, incident_id),
        )

    if temporal_client:
        await temporal_client.start_workflow(
            IncidentLifecycleWorkflow.run,
            incident_id,
            id=f"incident-{incident_id}",
            task_queue="incident-task-queue",
        )
        return {"accepted": True, "incident_id": incident_id, "status": "QUEUED_TEMPORAL"}
    else:
        return {"accepted": False, "incident_id": incident_id, "status": "NO_TEMPORAL_CLIENT"}

@app.post("/api/v2/incidents/{incident_id}/agent-findings")
def agent_findings(incident_id: str, payload: dict, current_user: User = Depends(get_current_user)):
    orchestrator = IncidentOrchestrator()
    res = orchestrator.save_agent_findings(incident_id, payload)
    return res

@app.get("/api/v2/incidents/{incident_id}/agent-logs")
def agent_logs(incident_id: str):
    import os
    log_file = f"logs/{incident_id}_nemoclaw.log"
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            return {"logs": f.read()}
    return {"logs": "Initializing NemoClaw Agent..."}

class ApprovalRequest(BaseModel):
    decision: str
    comment: Optional[str] = None
    plan_hash: str

class FeedbackRequest(BaseModel):
    feedback: str

@app.post("/api/v2/incidents/{incident_id}/feedback")
def submit_feedback(incident_id: str, req: FeedbackRequest, current_user: User = Depends(get_current_user)):
    orchestrator = IncidentOrchestrator()
    res = orchestrator.triage_feedback(incident_id, req.feedback)
    if "error" in res:
        raise HTTPException(status_code=500, detail=res["error"])
    return res

@app.post("/api/v2/incidents/{incident_id}/plans/{plan_id}/approve")
async def approve_plan(incident_id: str, plan_id: str, req: ApprovalRequest, current_user: User = Depends(get_current_user)):
    global temporal_client

    # Validate the plan_hash actually matches the current plan content (defense against stale/tampered approvals).
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    from src.domain.plan_hash import compute_plan_hash
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM action_plan WHERE action_plan_id = %s", (plan_id,))
        plan_row = cursor.fetchone()
        if not plan_row:
            raise HTTPException(status_code=404, detail="Plan not found")
        plan_cols = [c[0] for c in cursor.description]
        plan_dict = dict(zip(plan_cols, plan_row))
        cursor = conn.execute("SELECT * FROM action_step WHERE action_plan_id = %s ORDER BY sequence_no ASC", (plan_id,))
        step_cols = [c[0] for c in cursor.description]
        steps = [dict(zip(step_cols, r)) for r in cursor.fetchall()]

    expected_hash = compute_plan_hash(plan_dict, steps)
    if req.plan_hash != expected_hash:
        raise HTTPException(
            status_code=409,
            detail="Plan hash mismatch — the plan changed since it was presented for approval. Re-fetch and retry."
        )

    now = datetime.now(timezone.utc).isoformat()
    with db.get_connection() as conn:
        conn.execute("""
            INSERT INTO approval (approval_id, incident_id, action_plan_id, requested_at, expires_at, decision, decided_at, approver_id, plan_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (f"APP-{uuid.uuid4().hex[:8]}", incident_id, plan_id, now, now, req.decision, now, current_user.user_id, req.plan_hash))
        
        conn.execute("UPDATE action_plan SET status = 'APPROVED' WHERE action_plan_id = %s", (plan_id,))
        
        # Log audit
        conn.execute("""
            INSERT INTO audit_event (audit_event_id, incident_id, actor_type, actor_id, event_type, event_summary, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (f"AUD-{uuid.uuid4().hex[:8]}", incident_id, "HUMAN", current_user.user_id, "APPROVAL_RECORDED", "Action plan approved for execution", now))

    signaled = False
    if temporal_client:
        try:
            handle = temporal_client.get_workflow_handle(f"incident-{incident_id}")
            await handle.signal(IncidentLifecycleWorkflow.approve_plan, {"decision": req.decision, "plan_id": plan_id})
            signaled = True
        except Exception as e:
            print(f"Temporal signal failed (workflow may be stale/absent), falling back to direct execution: {e}")

    # Fallback: if we couldn't reach a live Temporal workflow, execute directly so the incident
    # doesn't get stuck in APPROVED forever (closes the gap documented in the architecture doc §8.3).
    if not signaled and req.decision == "approve":
        orchestrator = IncidentOrchestrator()
        orchestrator.execute_plan(incident_id, plan_id)
        return {"status": "executed_directly", "reason": "temporal_unavailable_or_stale"}

    return {"status": "signaled_temporal" if signaled else "success"}

@app.post("/api/v2/incidents/{incident_id}/plans/{plan_id}/execute")
async def execute_plan(incident_id: str, plan_id: str, current_user: User = Depends(require_role("commander"))):
    # Manual override / direct execution path (also used as fallback by /approve).
    orchestrator = IncidentOrchestrator()
    orchestrator.execute_plan(incident_id, plan_id)
    return {"status": "EXECUTING"}



@app.get("/api/v2/incidents/{incident_id}/events/stream")
async def stream_events(incident_id: str):
    async def event_generator():
        yield ": ping\n\n"
        db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
        last_ts = ""
        while True:
            with db.get_connection() as conn:
                try:
                    cursor = conn.execute(
                        "SELECT audit_event_id, created_at, actor_id, event_type, event_summary FROM audit_event WHERE incident_id = %s AND created_at > %s ORDER BY created_at ASC",
                        (incident_id, last_ts)
                    )
                    rows = cursor.fetchall()
                    for row in rows:
                        event_data = {
                            "id": row[0],
                            "timestamp": row[1],
                            "source": row[2],
                            "event_type": row[3],
                            "message": row[4]
                        }
                        yield f"data: {json.dumps(event_data)}\n\n"
                        last_ts = row[1]
                except Exception as e:
                    print(f"SSE Error: {e}")
            await asyncio.sleep(1)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
