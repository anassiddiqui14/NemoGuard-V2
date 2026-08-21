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
from src.api.auth import (
    get_current_user, require_role, require_any_role, User, get_mock_token,
    LoginRequest, verify_password, issue_token_for_user, IS_DEV_ENV,
)

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
    if not IS_DEV_ENV:
        raise HTTPException(status_code=404, detail="Not found")
    return {"access_token": get_mock_token(role), "token_type": "bearer"}

@app.get("/api/v2/auth/config")
def auth_config():
    """
    Tells the frontend how it is allowed to authenticate in THIS deployment.
    - dev_login_enabled: whether the no-credential mock-login endpoint is
      reachable at all (only true in development/dev/local).
    - credential_login_enabled: whether real email/password sign-in against
      platform_user is available (true whenever the table has at least one
      active account provisioned).
    This lets the login screen stop advertising "demo mode" / "skip login"
    as an option the moment a real deployment has real accounts, without any
    client-side toggle able to re-enable it.
    """
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    has_real_users = False
    try:
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM platform_user WHERE is_active = TRUE")
            has_real_users = cursor.fetchone()[0] > 0
    except Exception:
        has_real_users = False
    return {
        "dev_login_enabled": IS_DEV_ENV,
        "credential_login_enabled": has_real_users,
    }

@app.post("/api/v2/auth/login")
def login(req: LoginRequest):
    """
    Real credential-backed sign-in. Verifies the submitted password against
    the PBKDF2 hash stored for the account and, on success, issues a JWT
    carrying that account's actual roles/tenant/workspace -- replacing the
    mock-login flow where any typed password worked and the "role" was
    whatever the operator happened to click in a dropdown.
    """
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        cursor = conn.execute(
            "SELECT user_id, email, password_hash, roles, tenant_id, workspace_id, is_active FROM platform_user WHERE email = %s",
            (req.email.strip().lower(),),
        )
        row = cursor.fetchone()

    invalid_credentials = HTTPException(status_code=401, detail="Invalid email or password")
    if not row:
        raise invalid_credentials

    user_id, email, password_hash, roles, tenant_id, workspace_id, is_active = row
    if not is_active or not verify_password(req.password, password_hash):
        raise invalid_credentials

    token = issue_token_for_user({
        "user_id": user_id,
        "email": email,
        "roles": roles,
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
    })

    with db.get_connection() as conn:
        conn.execute(
            "UPDATE platform_user SET last_login_at = %s WHERE user_id = %s",
            (datetime.now(timezone.utc).isoformat(), user_id),
        )

    return {"access_token": token, "token_type": "bearer"}

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
            else:
                # init_schema() (which also runs apply_pending_migrations())
                # only runs on a genuinely fresh database -- but every
                # existing deployment restart previously skipped ALL
                # migration files entirely, since apply_pending_migrations()
                # was only ever called as a side effect of init_schema().
                # This silently meant new migrations (schema changes, new
                # tables) never reached any already-provisioned database
                # unless it happened to be wiped and recreated. Explicitly
                # re-run migrations on every startup for existing databases
                # too; every migration file uses CREATE TABLE IF NOT EXISTS /
                # ADD COLUMN IF NOT EXISTS guards, so this is safe/idempotent.
                print("Applying any pending migrations...")
                db.apply_pending_migrations()
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
            # Canonical severity values are stored with underscores (SEV_1,
            # SEV_2, ...) per the Severity enum (src/domain/enums.py) and the
            # CorrelatorEngine's severity_map, which writes Severity.SEV_1.value
            # == "SEV_1" into the incident.severity column. A previous version
            # of this query filtered on the hyphenated display form ("SEV-1"),
            # which never matches any stored row, silently zeroing out these
            # two KPIs. The frontend is responsible for rendering the
            # underscore form as hyphenated ("SEV-1") for display only.
            cur = conn.execute("SELECT COUNT(*) FROM incident WHERE status != 'RESOLVED' AND severity = 'SEV_1'")
            critical = cur.fetchone()[0]
            cur = conn.execute("SELECT COUNT(*) FROM incident WHERE status != 'RESOLVED' AND severity = 'SEV_2'")
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
def list_incidents(state: str = "open", current_user: User = Depends(get_current_user)):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        # Tenant scoping: every incident row carries a tenant_id (defaulted
        # to 'default_tenant' for all existing/single-tenant data), but no
        # query here previously filtered on it -- meaning any authenticated
        # user could enumerate/read every incident regardless of which
        # tenant's JWT they held. Scoping by current_user.tenant_id is safe
        # for the existing single-tenant deployment (all rows already carry
        # 'default_tenant') and closes the leak the moment a second tenant
        # exists.
        # Include resolved_at so the frontend can show "time to resolve" for
        # resolved incidents instead of a live-ticking elapsed-time clock that
        # keeps counting up forever even after the incident is closed.
        if state == "open":
            # FAILED is terminal as well: the recovery attempt has completed
            # but independent verification did not pass, so it must be worked
            # from the escalation/history view rather than presented as an
            # unchanged active incident in the operator queue.
            cursor = conn.execute(
                "SELECT incident_id, title, status, severity, detected_at, next_sla_breach_at, owner_team, primary_job_id, summary, resolved_at "
                "FROM incident WHERE tenant_id = %s AND status NOT IN ('RESOLVED', 'FAILED', 'CLOSED', 'CANCELLED') ORDER BY detected_at DESC",
                (current_user.tenant_id,),
            )
        else:
            cursor = conn.execute(
                "SELECT incident_id, title, status, severity, detected_at, next_sla_breach_at, owner_team, primary_job_id, summary, resolved_at "
                "FROM incident WHERE tenant_id = %s ORDER BY detected_at DESC",
                (current_user.tenant_id,),
            )
            
        cols = [col[0] for col in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

# --- 12.2 Incident detail endpoints ---

@app.get("/api/v2/incidents/{incident_id}")
def get_incident(incident_id: str, current_user: User = Depends(get_current_user)):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM incident WHERE incident_id = %s AND tenant_id = %s",
            (incident_id, current_user.tenant_id),
        )
        row = cursor.fetchone()
        if not row:
            # Deliberately returns 404 (not 403) whether the incident simply
            # doesn't exist OR belongs to another tenant -- avoids confirming
            # to a caller that an incident ID they don't have access to
            # actually exists in some other tenant.
            raise HTTPException(status_code=404, detail="Incident not found")
        cols = [col[0] for col in cursor.description]
        return dict(zip(cols, row))

@app.get("/api/v2/incidents/{incident_id}/summary")
def get_incident_summary(incident_id: str, current_user: User = Depends(get_current_user)):
    # For now, just return the incident details
    return get_incident(incident_id, current_user)

@app.get("/api/v2/incidents/{incident_id}/hypotheses")
def get_hypotheses(incident_id: str, current_user: User = Depends(get_current_user)):
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
def get_evidence(incident_id: str, current_user: User = Depends(get_current_user)):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM evidence WHERE incident_id = %s ORDER BY collected_at ASC", (incident_id,))
        cols = [col[0] for col in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

@app.get("/api/v2/incidents/{incident_id}/impact")
def get_impact(incident_id: str, current_user: User = Depends(get_current_user)):
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
def get_plans(incident_id: str, current_user: User = Depends(get_current_user)):
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
def get_events(incident_id: str, current_user: User = Depends(get_current_user)):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM audit_event WHERE incident_id = %s ORDER BY created_at ASC", (incident_id,))
        cols = [col[0] for col in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

@app.get("/api/v2/incidents/{incident_id}/alerts")
def get_incident_alerts(incident_id: str, current_user: User = Depends(get_current_user)):
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
def get_all_alerts(current_user: User = Depends(get_current_user)):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM alert ORDER BY opened_ts DESC")
        cols = [col[0] for col in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

# --- 12.3 Context Endpoints (for NemoClaw Agents) ---

@app.get("/api/v2/context/alerts/{incident_id}")
def get_incident_alerts_context(incident_id: str, current_user: User = Depends(get_current_user)):
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
def get_incident_logs_context(incident_id: str, current_user: User = Depends(get_current_user)):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT primary_run_id FROM incident WHERE incident_id = %s", (incident_id,))
        run_id_row = cursor.fetchone()
        if run_id_row and run_id_row[0]:
            cursor = conn.execute("SELECT message FROM log_event WHERE run_id = %s", (run_id_row[0],))
            return [row[0] for row in cursor.fetchall()]
        return []

@app.get("/api/v2/context/cmdb")
def get_cmdb_context(current_user: User = Depends(get_current_user)):
    import json
    with open("data/mock_dimensions/cmdb.json", "r") as f:
        return json.load(f)

@app.get("/api/v2/context/runbooks")
def get_runbooks_context(current_user: User = Depends(get_current_user)):
    import json
    with open("data/mock_dimensions/runbooks.json", "r") as f:
        return json.load(f)

# --- 12.4 Workflow endpoints ---

@app.post("/api/v2/ingest/webhook")
async def ingest_webhook(payload: dict, request: Request):
    """
    Generic webhook endpoint for Datadog, PagerDuty, or Email-to-Webhook parsing.
    Passes the payload to the WatcherAgent to determine if it's a valid alert.

    This endpoint is intentionally left open to unauthenticated callers
    (real monitoring systems can't easily be issued NemoGuard JWTs), but is
    now bounded by:
      - a per-source-IP sliding-window rate limit (see rate_limit.py)
      - a maximum payload size / nesting depth / string length (see
        webhook_validation.py) before the payload is ever handed to an LLM.
    """
    from src.api.rate_limit import enforce_webhook_rate_limit
    from src.api.webhook_validation import validate_webhook_payload

    enforce_webhook_rate_limit(request)
    validate_webhook_payload(payload)

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
async def triage_incident(incident_id: str, current_user: User = Depends(require_role("operator"))):
    """
    Triage can take a long time, so we schedule it in Temporal.
    """
    global temporal_client
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    from src.domain.incident_state_service import IncidentStateService, IncidentNotFoundError
    from src.domain.state_machine import InvalidTransitionError
    state_service = IncidentStateService(db)
    try:
        state_service.transition(
            incident_id=incident_id, to=IncidentState.INVESTIGATING,
            actor=current_user.user_id, reason="Manual triage requested via API.",
        )
    except IncidentNotFoundError:
        raise HTTPException(status_code=404, detail="Incident not found")
    except InvalidTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))

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
def agent_findings(incident_id: str, payload: dict, current_user: User = Depends(require_role("operator"))):
    orchestrator = IncidentOrchestrator()
    res = orchestrator.save_agent_findings(incident_id, payload)
    return res

@app.get("/api/v2/incidents/{incident_id}/agent-logs")
def agent_logs(incident_id: str, current_user: User = Depends(get_current_user)):
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
def submit_feedback(incident_id: str, req: FeedbackRequest, current_user: User = Depends(require_role("operator"))):
    orchestrator = IncidentOrchestrator()
    res = orchestrator.triage_feedback(incident_id, req.feedback, submitted_by=current_user.user_id)
    if "error" in res:
        raise HTTPException(status_code=500, detail=res["error"])
    return res

@app.post("/api/v2/incidents/{incident_id}/plans/{plan_id}/approve")
async def approve_plan(incident_id: str, plan_id: str, req: ApprovalRequest, current_user: User = Depends(require_role("approver"))):
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


# ---------------------------------------------------------------------------
# Admin: Capability catalog + policy administration (spec §17.3/§17.4).
# Lets an admin see exactly what real capabilities are registered, what
# their EFFECTIVE (post-override) policy is, and force a live reload of
# config/capability_policy.yaml without a process restart -- all admin-only.
# ---------------------------------------------------------------------------

@app.get("/api/v2/admin/capabilities")
async def list_capabilities(current_user: User = Depends(require_role("admin"))):
    from src.capabilities import registry, policy
    from src.capabilities.models import CompiledAction, RiskLevel, AutonomyMode

    results = []
    for definition in registry.list_capabilities():
        # Build a throwaway CompiledAction just to run it through the same
        # effective-policy resolution the real execution engine uses, so
        # what the admin sees here is GUARANTEED to match runtime behavior
        # (no separate/divergent "display" logic).
        fake_action = CompiledAction(
            action_id="ADMIN-PREVIEW",
            sequence=1,
            capability_id=definition.capability_id,
            capability_version=definition.version,
            intent_type="ADMIN_PREVIEW",
            target_resource_type="N/A",
            target_resource_id="N/A",
            arguments={},
            risk_level=definition.risk_level,
            autonomy_mode=definition.autonomy_mode,
            supports_dry_run=definition.supports_dry_run,
            idempotency_key="admin-preview",
        )
        effective_risk, effective_autonomy = policy._effective_risk_and_autonomy(fake_action)
        results.append({
            "capability_id": definition.capability_id,
            "version": definition.version,
            "kind": definition.kind.value,
            "description": definition.description,
            "owner": definition.owner,
            "default_risk_level": definition.risk_level.value,
            "default_autonomy_mode": definition.autonomy_mode.value,
            "effective_risk_level": effective_risk.value,
            "effective_autonomy_mode": effective_autonomy.value,
            "overridden": (effective_risk != definition.risk_level) or (effective_autonomy != definition.autonomy_mode),
            "supports_dry_run": definition.supports_dry_run,
            "required_args": definition.required_args,
        })
    return results


@app.post("/api/v2/admin/capabilities/reload-policy")
async def reload_capability_policy(current_user: User = Depends(require_role("admin"))):
    from src.capabilities import policy
    policy.reload_policy_config()
    return {"status": "reloaded", "config_path": str(policy._CONFIG_PATH)}



@app.get("/api/v2/incidents/{incident_id}/events/stream")
async def stream_events(incident_id: str, token: Optional[str] = None):
    # EventSource (used by the frontend's SSE client) cannot send custom
    # Authorization headers, so the token must be passed as a query param.
    # This endpoint was previously completely unauthenticated -- any
    # network-reachable client could read the full live agent-reasoning /
    # audit trail for any incident. Validate the token the same way
    # get_current_user does, just via query param instead of a header.
    import jwt as _jwt
    from src.api.auth import SECRET_KEY, ALGORITHM
    if not token:
        raise HTTPException(status_code=401, detail="Missing token query parameter")
    try:
        _jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except _jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except _jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

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
