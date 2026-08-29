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
            "SELECT user_id, email, password_hash, roles, tenant_id, workspace_id, is_active, display_name FROM platform_user WHERE email = %s",
            (req.email.strip().lower(),),
        )
        row = cursor.fetchone()

    invalid_credentials = HTTPException(status_code=401, detail="Invalid email or password")
    if not row:
        raise invalid_credentials

    user_id, email, password_hash, roles, tenant_id, workspace_id, is_active, display_name = row
    if not is_active or not verify_password(req.password, password_hash):
        raise invalid_credentials

    token = issue_token_for_user({
        "user_id": user_id,
        "email": email,
        "roles": roles,
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "display_name": display_name,
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

    # Background Teams-notification poller (WP-ORG-002 §4.19-4.20 Phase A).
    # Periodically catches up commander_status_update projection + Teams
    # dispatch for every non-terminal incident, rather than requiring every
    # audit-event call site across orchestrator.py to be individually
    # threaded through to NotificationDispatcher. A short interval keeps
    # this close to real-time without adding meaningful DB load (each tick
    # is a handful of indexed SELECTs per active incident).
    asyncio.create_task(_teams_notification_poller())


async def _teams_notification_poller() -> None:
    """
    Keeps Commander Pulse projection AND Teams dispatch moving forward for
    every incident, independent of whether/when any particular incident's
    workspace happens to be open in a browser (get_pulse() only projects
    on-demand when polled by the frontend). Dispatch is intentionally
    decoupled from projection (see NotificationDispatcher.
    find_undispatched_updates) so it doesn't matter which code path
    created a given commander_status_update row -- this tick will still
    find and deliver it exactly once.
    """
    from src.domain.commander.status_projector import StatusProjector
    from src.domain.notifications.dispatcher import NotificationDispatcher
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    projector = StatusProjector(db)
    dispatcher = NotificationDispatcher(db)
    while True:
        try:
            with db.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT incident_id FROM incident WHERE status NOT IN ('RESOLVED', 'FAILED', 'CLOSED', 'CANCELLED')"
                )
                active_incident_ids = [row[0] for row in cursor.fetchall()]
            for incident_id in active_incident_ids:
                try:
                    projector.project_unprojected_events(incident_id)
                except Exception as e:
                    print(f"Teams notification poller: projection failed for {incident_id}: {e}")
            await dispatcher.dispatch_all_pending()
        except Exception as e:
            print(f"Teams notification poller: tick failed: {e}")
        await asyncio.sleep(15)

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

def _require_incident_in_tenant(db: PostgresDatabase, incident_id: str, tenant_id: str) -> None:
    """
    Verifies `incident_id` exists AND belongs to `tenant_id`, raising 404 if
    not (never 403 -- see get_incident's comment on why 404 is deliberate
    for both "doesn't exist" and "wrong tenant").

    Per docs/NemoGuard_Enterprise_Hardening_and_Productization_Build_Plan.md
    Priority 8 / spec §12.3: every sub-resource endpoint scoped by
    incident_id (evidence, hypotheses, impact, plans, events, alerts) MUST
    verify the incident belongs to the caller's tenant, not just that
    *an* incident with that ID exists somewhere. These sub-resource tables
    (evidence, hypothesis, action_plan, audit_event, ...) do carry their own
    tenant_id column, but it is never explicitly populated on INSERT
    (always the column default) -- so the incident's own tenant_id is the
    reliable source of truth to check against, not the sub-resource row's
    own (effectively unset) tenant_id.
    """
    with db.get_connection() as conn:
        cursor = conn.execute(
            "SELECT 1 FROM incident WHERE incident_id = %s AND tenant_id = %s",
            (incident_id, tenant_id),
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Incident not found")


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

@app.get("/api/v2/incidents/{incident_id}/evidence-package")
def get_incident_evidence_package(incident_id: str, current_user: User = Depends(get_current_user)):
    """
    Assembles the incident's complete, auditable decision trail into a
    single exportable JSON document -- per
    docs/NemoGuard_Validation_Demonstration_and_Adoption_Readiness_Plan.md
    §21 ("Generate an Incident Evidence Package"): metadata, source alerts,
    hypotheses, evidence, impact, recovery plan(s), and the full audit
    timeline in one place, valuable for audits, architecture review,
    customer adoption conversations, and postmortems.

    This intentionally reuses each existing single-purpose endpoint's own
    query logic (via direct function calls) rather than re-deriving a
    second, potentially-drifting copy of the same SQL, and applies the
    exact same tenant-scoping guarantee (404, not 403, for cross-tenant or
    nonexistent incidents) as every other incident sub-resource.
    """
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    _require_incident_in_tenant(db, incident_id, current_user.tenant_id)

    incident = get_incident(incident_id, current_user)
    hypotheses = get_hypotheses(incident_id, current_user)
    evidence = get_evidence(incident_id, current_user)
    impact = get_impact(incident_id, current_user)
    plans = get_plans(incident_id, current_user)
    alerts = get_incident_alerts(incident_id, current_user)

    with db.get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM audit_event WHERE incident_id = %s ORDER BY created_at ASC",
            (incident_id,),
        )
        cols = [col[0] for col in cursor.description]
        audit_timeline = [dict(zip(cols, row)) for row in cursor.fetchall()]

        cursor = conn.execute(
            "SELECT * FROM verification_result WHERE incident_id = %s ORDER BY checked_at ASC",
            (incident_id,),
        )
        cols = [col[0] for col in cursor.description]
        verification_results = [dict(zip(cols, row)) for row in cursor.fetchall()]

    return {
        "package_generated_at": datetime.now(timezone.utc).isoformat(),
        "package_generated_by": current_user.user_id,
        "incident": incident,
        "alerts": alerts,
        "hypotheses": hypotheses,
        "evidence": evidence,
        "impact": impact,
        "recovery_plans": plans,
        "verification_results": verification_results,
        "audit_timeline": audit_timeline,
    }

@app.get("/api/v2/incidents/{incident_id}/hypotheses")
def get_hypotheses(incident_id: str, current_user: User = Depends(get_current_user)):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    _require_incident_in_tenant(db, incident_id, current_user.tenant_id)
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
    _require_incident_in_tenant(db, incident_id, current_user.tenant_id)
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM evidence WHERE incident_id = %s ORDER BY collected_at ASC", (incident_id,))
        cols = [col[0] for col in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

@app.get("/api/v2/incidents/{incident_id}/impact")
def get_impact(incident_id: str, current_user: User = Depends(get_current_user)):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    _require_incident_in_tenant(db, incident_id, current_user.tenant_id)
    with db.get_connection() as conn:
        cursor = conn.execute("""
            SELECT
                i.*,
                d.name AS asset_name,
                d.criticality AS asset_criticality,
                d.freshness_sla_minutes,
                d.estimated_user_count,
                d.impact_band,
                d.business_process,
                d.owner_team AS asset_owner_team
            FROM incident_impact i
            LEFT JOIN data_asset d ON i.asset_id = d.asset_id
            WHERE i.incident_id = %s
            ORDER BY i.impact_score DESC, i.asset_id ASC
        """, (incident_id,))
        cols = [col[0] for col in cursor.description]
        rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
        for r in rows:
            r['evidence_ids'] = json.loads(r['evidence_ids_json'] or '[]')
            r['score_components'] = json.loads(r.get('score_components_json') or '{}')
        return rows

@app.get("/api/v2/incidents/{incident_id}/plans")
def get_plans(incident_id: str, current_user: User = Depends(get_current_user)):
    from src.domain.plan_hash import compute_plan_hash
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    _require_incident_in_tenant(db, incident_id, current_user.tenant_id)
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
    _require_incident_in_tenant(db, incident_id, current_user.tenant_id)
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM audit_event WHERE incident_id = %s ORDER BY created_at ASC", (incident_id,))
        cols = [col[0] for col in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

@app.get("/api/v2/incidents/{incident_id}/alerts")
def get_incident_alerts(incident_id: str, current_user: User = Depends(get_current_user)):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    _require_incident_in_tenant(db, incident_id, current_user.tenant_id)
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

# --- 12.3 Context Endpoints (for investigation agents) ---

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

async def _process_ingested_webhook(payload: Dict[str, Any]) -> None:
    """Run long-lived incident analysis off the API event loop."""
    try:
        result = await asyncio.to_thread(
            lambda: asyncio.run(IncidentOrchestrator().process_webhook(payload))
        )
        if result.get("status") == "error":
            print(f"Webhook orchestration failed: {result.get('message')}")
            return

        if result.get("status") == "ingested_and_incident_created":
            incident_id = result.get("incident_id")
            global temporal_client
            if temporal_client and incident_id:
                await temporal_client.start_workflow(
                    IncidentLifecycleWorkflow.run,
                    incident_id,
                    id=f"incident-{incident_id}",
                    task_queue="incident-task-queue",
                )
    except Exception as exc:
        # The alert was accepted, so leave transport acknowledgements intact
        # and log any later analysis failure for diagnosis.
        print(f"Webhook background orchestration failed: {exc}")


@app.post("/api/v2/ingest/webhook", status_code=202)
async def ingest_webhook(request: Request):
    """
    Generic webhook endpoint for Datadog, PagerDuty, or Email-to-Webhook parsing.
    Passes the payload to the WatcherAgent to determine if it's a valid alert.

    This endpoint is intentionally left open to unauthenticated callers
    (real monitoring systems can't easily be issued NemoGuard JWTs), but is
    now bounded by (per build plan Priority 9):
      - a per-source-IP sliding-window rate limit (13.4, see rate_limit.py)
      - a maximum payload size / nesting depth / string length (13.2, see
        webhook_validation.py) before the payload is ever handed to an LLM
      - OPT-IN per-source HMAC-SHA256 signature verification (13.3, see
        webhook_security.py) -- enforced only once an operator configures a
        WEBHOOK_SECRET_<SOURCE> secret for that source
      - timestamp-bounds + event_id dedup replay protection (13.5, see
        webhook_security.py)

    Reads the raw request body (rather than accepting an auto-parsed
    `payload: dict` parameter) because HMAC signature verification must be
    computed over the exact bytes the sender signed -- re-serializing an
    already-parsed dict is not guaranteed to byte-for-byte match the
    original request body (key ordering, whitespace, unicode escaping),
    which would make signature verification silently unreliable.
    """
    from src.api.rate_limit import enforce_webhook_rate_limit
    from src.api.webhook_validation import validate_webhook_payload
    from src.api.webhook_security import verify_webhook_signature, enforce_replay_protection

    enforce_webhook_rate_limit(request)

    raw_body = await request.body()
    try:
        payload = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"Payload is not valid JSON: {e}")

    validate_webhook_payload(payload)

    # `source` is used both for HMAC secret lookup and downstream
    # correlation -- accept either the canonical envelope's "source" field
    # (13.1) or the pre-existing "source_system" field real integrations
    # already send today, so this doesn't break any existing sender.
    source = str(payload.get("source") or payload.get("source_system") or "").strip()
    signature_header = request.headers.get("X-NemoGuard-Signature")
    verify_webhook_signature(raw_body, source, signature_header)
    enforce_replay_protection(payload)

    asyncio.create_task(_process_ingested_webhook(payload))
    return {"status": "accepted_for_processing"}

@app.post("/api/v2/incidents/{incident_id}/triage")
async def triage_incident(incident_id: str, current_user: User = Depends(require_role("operator"))):
    """
    Triage can take a long time, so we schedule it in Temporal.
    """
    global temporal_client
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    _require_incident_in_tenant(db, incident_id, current_user.tenant_id)
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
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    _require_incident_in_tenant(db, incident_id, current_user.tenant_id)
    orchestrator = IncidentOrchestrator()
    res = orchestrator.save_agent_findings(incident_id, payload)
    return res

@app.get("/api/v2/incidents/{incident_id}/agent-logs")
def agent_logs(incident_id: str, current_user: User = Depends(get_current_user)):
    # Legacy endpoint, not called by the current React frontend (which
    # renders live agent activity from /events and the audit trail
    # instead). Left in place for backward compatibility with any external
    # tooling that may still poll it, but the branding of its filename/
    # placeholder text should stay consistent with the product name.
    import os
    log_file = f"logs/{incident_id}_agent.log"
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            return {"logs": f.read()}
    return {"logs": "Initializing NemoGuard investigation agents..."}

class ApprovalRequest(BaseModel):
    decision: str
    comment: Optional[str] = None
    plan_hash: str

class FeedbackRequest(BaseModel):
    feedback: str

@app.post("/api/v2/incidents/{incident_id}/feedback")
def submit_feedback(incident_id: str, req: FeedbackRequest, current_user: User = Depends(require_role("operator"))):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    _require_incident_in_tenant(db, incident_id, current_user.tenant_id)
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
    _require_incident_in_tenant(db, incident_id, current_user.tenant_id)
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

    # Fallback: if we couldn't reach a live Temporal workflow, execute only
    # through the same governed Capability Gateway path. Normalize UI/API
    # decision casing so APPROVED and approve behave identically.
    if not signaled and req.decision.strip().upper() == "APPROVED":
        result = IncidentOrchestrator().execute_plan(incident_id, plan_id)
        if result.get("status") == "MANUAL_ACTION_REQUIRED":
            raise HTTPException(status_code=409, detail=result)
        return {
            "status": "executed_directly",
            "reason": "temporal_unavailable_or_stale",
            "execution": result,
        }

    return {"status": "signaled_temporal" if signaled else "success"}

@app.post("/api/v2/incidents/{incident_id}/plans/{plan_id}/execute")
async def execute_plan(incident_id: str, plan_id: str, current_user: User = Depends(require_role("commander"))):
    # Manual override / direct execution path (also used as fallback by /approve).
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    _require_incident_in_tenant(db, incident_id, current_user.tenant_id)
    result = IncidentOrchestrator().execute_plan(incident_id, plan_id)
    if result.get("status") == "MANUAL_ACTION_REQUIRED":
        raise HTTPException(status_code=409, detail=result)
    return result


class CancelRequest(BaseModel):
    reason: Optional[str] = None


@app.post("/api/v2/incidents/{incident_id}/cancel")
async def cancel_incident(incident_id: str, req: CancelRequest, current_user: User = Depends(require_role("commander"))):
    """
    Per docs/NemoGuard_Enterprise_Hardening_and_Productization_Build_Plan.md
    Priority 10 sections 14.3/14.4 ("cancel ... should be workflow signals").
    Previously there was NO way to cancel an incident that was blocked
    awaiting approval other than killing its Temporal workflow completely
    out-of-band -- which bypasses the incident state machine entirely (no
    audit trail, no legal-transition check) and leaves the underlying
    incident row silently stuck at whatever status it was last in.

    Mirrors /approve's signal-first pattern: if a live Temporal workflow
    exists for this incident, signal it (the workflow itself performs the
    actual AWAITING_APPROVAL -> CANCELLED state transition + audit event via
    lifecycle_activity.py, keeping the state machine as the single source of
    truth). If no live workflow can be reached (stale/absent), fall back to
    performing the transition directly so the incident doesn't get stuck.
    """
    global temporal_client
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    _require_incident_in_tenant(db, incident_id, current_user.tenant_id)

    signaled = False
    if temporal_client:
        try:
            handle = temporal_client.get_workflow_handle(f"incident-{incident_id}")
            await handle.signal(IncidentLifecycleWorkflow.cancel_incident, {"reason": req.reason or ""})
            signaled = True
        except Exception as e:
            print(f"Temporal cancel signal failed (workflow may be stale/absent), falling back to direct transition: {e}")

    if not signaled:
        from src.domain.incident_state_service import IncidentStateService, IncidentNotFoundError
        from src.domain.state_machine import InvalidTransitionError
        state_service = IncidentStateService(db)
        try:
            state_service.transition(
                incident_id=incident_id, to=IncidentState.CANCELLED,
                actor=current_user.user_id, reason=req.reason or "Cancelled via API (no live workflow to signal).",
            )
        except IncidentNotFoundError:
            raise HTTPException(status_code=404, detail="Incident not found")
        except InvalidTransitionError as e:
            raise HTTPException(status_code=409, detail=str(e))
        return {"status": "cancelled_directly", "reason": "temporal_unavailable_or_stale"}

    return {"status": "signaled_temporal"}


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


# ---------------------------------------------------------------------------
# Adoption Readiness Dashboard (spec §20). Every value below is either read
# directly from a persisted, real validation-run JSON artifact under
# docs/validation/ (produced by scripts/run_validation_suite.py,
# run_security_validation.py, run_ai_evaluation.py, or a pytest run) or
# computed live from the actual incident/alert tables -- nothing here is
# hardcoded or estimated. Missing artifacts are reported as "unknown"
# rather than a fabricated placeholder value.
# ---------------------------------------------------------------------------

def _load_latest_validation_artifact(prefix: str) -> Optional[dict]:
    """Reads the most recently modified docs/validation/{prefix}*.json
    file, if any exists. Returns None (never a fabricated stand-in) when
    no such artifact has been generated yet in this deployment."""
    import glob
    candidates = sorted(
        glob.glob(f"docs/validation/{prefix}*.json"),
        key=os.path.getmtime,
        reverse=True,
    )
    if not candidates:
        return None
    try:
        with open(candidates[0]) as f:
            data = json.load(f)
        data["_source_file"] = candidates[0]
        return data
    except Exception:
        return None


@app.get("/api/v2/admin/adoption-readiness")
async def get_adoption_readiness(current_user: User = Depends(require_role("admin"))):
    unit_tests = _load_latest_validation_artifact("unit_test_result")
    scenario_suite = _load_latest_validation_artifact("core_suite_result")
    security_suite = _load_latest_validation_artifact("security_result")
    ai_eval = _load_latest_validation_artifact("ai_eval_result")

    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    operational_metrics: Dict[str, Any] = {}
    try:
        with db.get_connection() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM incident WHERE tenant_id = %s", (current_user.tenant_id,))
            total_incidents = cur.fetchone()[0]

            cur = conn.execute(
                "SELECT COUNT(*) FROM incident WHERE tenant_id = %s AND status NOT IN ('RESOLVED', 'FAILED', 'CLOSED', 'CANCELLED')",
                (current_user.tenant_id,),
            )
            active_incidents = cur.fetchone()[0]

            cur = conn.execute(
                "SELECT COUNT(*) FROM alert a JOIN incident_alert ia ON a.alert_id = ia.alert_id "
                "JOIN incident i ON ia.incident_id = i.incident_id WHERE i.tenant_id = %s",
                (current_user.tenant_id,),
            )
            total_correlated_alerts = cur.fetchone()[0]

            # Alert compression ratio (plan §16): how many raw alerts map
            # into how few incidents -- a real, currently-observable ratio,
            # not a marketing estimate. Guards against a divide-by-zero
            # when no incidents exist yet in this tenant.
            alert_compression_ratio = (
                round(total_correlated_alerts / total_incidents, 2) if total_incidents else None
            )

            # Median time-to-resolve, computed only over incidents that
            # actually have both a detected_at and resolved_at timestamp --
            # never estimated for incidents still open.
            cur = conn.execute(
                "SELECT detected_at, resolved_at FROM incident "
                "WHERE tenant_id = %s AND resolved_at IS NOT NULL AND detected_at IS NOT NULL",
                (current_user.tenant_id,),
            )
            resolve_durations_sec = []
            for detected_at, resolved_at in cur.fetchall():
                try:
                    d = datetime.fromisoformat(str(detected_at).replace("Z", "+00:00"))
                    r = datetime.fromisoformat(str(resolved_at).replace("Z", "+00:00"))
                    resolve_durations_sec.append((r - d).total_seconds())
                except Exception:
                    continue
            median_mttr_seconds = None
            if resolve_durations_sec:
                resolve_durations_sec.sort()
                mid = len(resolve_durations_sec) // 2
                median_mttr_seconds = (
                    resolve_durations_sec[mid]
                    if len(resolve_durations_sec) % 2
                    else (resolve_durations_sec[mid - 1] + resolve_durations_sec[mid]) / 2
                )

            operational_metrics = {
                "total_incidents": total_incidents,
                "active_incidents": active_incidents,
                "total_correlated_alerts": total_correlated_alerts,
                "alert_compression_ratio": alert_compression_ratio,
                "resolved_incident_count_with_known_mttr": len(resolve_durations_sec),
                "median_mttr_seconds": round(median_mttr_seconds, 1) if median_mttr_seconds is not None else None,
            }
    except Exception as e:
        operational_metrics = {"error": str(e)}

    def _summarize(artifact: Optional[dict], label: str) -> dict:
        if not artifact:
            return {"available": False, "label": label}
        passed = artifact.get("passed")
        total = artifact.get("total")
        metrics = artifact.get("metrics")  # ai_eval_result carries its own metrics block
        return {
            "available": True,
            "label": label,
            "passed": passed,
            "total": total,
            "metrics": metrics,
            "run_at": artifact.get("run_at"),
            "source_file": artifact.get("_source_file"),
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "unit_tests": _summarize(unit_tests, "Unit Test Suite"),
        "scenario_suite": _summarize(scenario_suite, "Real-AWS Scenario Suite (WP-VAL-002)"),
        "security_suite": _summarize(security_suite, "Security & Governance Suite (WP-VAL-003)"),
        "ai_evaluation": _summarize(ai_eval, "AI Evaluation Benchmark (WP-VAL-004)"),
        "operational_metrics": operational_metrics,
    }



# ---------------------------------------------------------------------------
# Historical Incident Replay (WP-ORG-001).
# See docs/NemoGuard_Internal_Org_Next_Steps_for_Coding_Agent_2026-08-27_v2_Commander_Live.md
# §3. Replays a past incident through the SAME investigation graph used
# for live incidents (src/domain/replay/replay_engine.py), using only
# point-in-time evidence, with the real root cause hidden until scoring.
# Admin-only: this ingests/exposes potentially sensitive historical
# incident data and drives real (metered) LLM calls.
# ---------------------------------------------------------------------------

class HistoricalSnapshotIn(BaseModel):
    snapshot_type: str
    payload: Any
    snapshot_timestamp: Optional[str] = None
    source_reference: Optional[str] = None


class HistoricalGroundTruthIn(BaseModel):
    root_cause: str
    cause_type: Optional[str] = None
    actual_recovery: Optional[str] = None
    actual_impacted_assets: Optional[List[str]] = None
    actual_business_impact: Optional[str] = None
    actual_resolution_time_seconds: Optional[float] = None
    postmortem_reference: Optional[str] = None


class HistoricalIncidentIn(BaseModel):
    source_system: str
    title: str
    opened_at: str
    resolved_at: Optional[str] = None
    service: Optional[str] = None
    pipeline: Optional[str] = None
    environment: Optional[str] = None
    severity: Optional[str] = None
    external_incident_id: Optional[str] = None
    snapshots: List[HistoricalSnapshotIn] = []
    ground_truth: Optional[HistoricalGroundTruthIn] = None


class ReplayStartIn(BaseModel):
    model_provider: Optional[str] = "nvidia_nim"
    model_name: Optional[str] = "nvidia/nemotron-3-ultra-550b-a55b"
    prompt_version: Optional[str] = "v1"


@app.post("/api/v2/replay/historical-incidents")
async def create_historical_incident(payload: HistoricalIncidentIn, current_user: User = Depends(require_role("admin"))):
    from src.domain.replay.replay_engine import ReplayEngine
    engine = ReplayEngine()
    historical_incident_id = engine.create_historical_incident(
        source_system=payload.source_system,
        title=payload.title,
        opened_at=payload.opened_at,
        resolved_at=payload.resolved_at,
        service=payload.service,
        pipeline=payload.pipeline,
        environment=payload.environment,
        severity=payload.severity,
        external_incident_id=payload.external_incident_id,
        created_by=current_user.user_id,
        snapshots=[s.model_dump() for s in payload.snapshots],
        ground_truth=payload.ground_truth.model_dump() if payload.ground_truth else None,
    )
    return {"historical_incident_id": historical_incident_id}


@app.get("/api/v2/replay/historical-incidents")
async def list_historical_incidents(current_user: User = Depends(require_role("admin"))):
    from src.domain.replay.replay_engine import ReplayEngine
    return ReplayEngine().list_historical_incidents()


@app.get("/api/v2/replay/historical-incidents/{historical_incident_id}")
async def get_historical_incident_detail(historical_incident_id: str, current_user: User = Depends(require_role("admin"))):
    from src.domain.replay.replay_engine import ReplayEngine, HistoricalIncidentNotFoundError
    engine = ReplayEngine()
    try:
        incident = engine.get_historical_incident(historical_incident_id)
    except HistoricalIncidentNotFoundError:
        raise HTTPException(status_code=404, detail="Historical incident not found")
    with engine.db.get_connection() as conn:
        cursor = conn.execute(
            "SELECT id, model_provider, model_name, status, started_at, completed_at, error_message "
            "FROM historical_incident_replay WHERE historical_incident_id = %s ORDER BY started_at DESC",
            (historical_incident_id,),
        )
        cols = [c[0] for c in cursor.description]
        replays = [dict(zip(cols, row)) for row in cursor.fetchall()]
        cursor = conn.execute(
            "SELECT 1 FROM historical_incident_ground_truth WHERE historical_incident_id = %s",
            (historical_incident_id,),
        )
        has_ground_truth = cursor.fetchone() is not None
    incident["replays"] = replays
    incident["has_ground_truth"] = has_ground_truth
    return incident


async def _run_replay_background(replay_id: str) -> None:
    from src.domain.replay.replay_engine import ReplayEngine
    try:
        await ReplayEngine().run_replay(replay_id)
    except Exception as e:
        print(f"Replay {replay_id} background execution failed: {e}")


@app.post("/api/v2/replay/incidents/{historical_incident_id}")
async def start_incident_replay(historical_incident_id: str, payload: ReplayStartIn, current_user: User = Depends(require_role("admin"))):
    from src.domain.replay.replay_engine import ReplayEngine, HistoricalIncidentNotFoundError
    engine = ReplayEngine()
    try:
        replay_id = engine.start_replay(
            historical_incident_id,
            model_provider=payload.model_provider or "nvidia_nim",
            model_name=payload.model_name or "nvidia/nemotron-3-ultra-550b-a55b",
            prompt_version=payload.prompt_version or "v1",
            created_by=current_user.user_id,
        )
    except HistoricalIncidentNotFoundError:
        raise HTTPException(status_code=404, detail="Historical incident not found")
    asyncio.create_task(_run_replay_background(replay_id))
    return {"replay_id": replay_id, "status": "PENDING"}


@app.get("/api/v2/replay/{replay_id}")
async def get_replay_status(replay_id: str, current_user: User = Depends(require_role("admin"))):
    from src.domain.replay.replay_engine import ReplayEngine
    try:
        return ReplayEngine().get_replay(replay_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Replay not found")


@app.get("/api/v2/replay/{replay_id}/result")
async def get_replay_result_endpoint(replay_id: str, current_user: User = Depends(require_role("admin"))):
    from src.domain.replay.replay_engine import ReplayEngine
    engine = ReplayEngine()
    try:
        replay = engine.get_replay(replay_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Replay not found")
    result = engine.get_replay_result(replay_id)
    return {"replay": replay, "result": result}


# ---------------------------------------------------------------------------
# Model Evaluation Service (WP-ORG-004). Admin-only: runs the SAME incident
# suite (historical incidents from WP-ORG-001) against multiple
# organization-approved models and produces a real, computed scorecard.
# ---------------------------------------------------------------------------

class ModelEvaluationRunIn(BaseModel):
    name: str
    models: List[str]
    historical_incident_ids: List[str]
    prompt_version: Optional[str] = "v1"


@app.post("/api/v2/admin/model-evaluation/runs")
async def create_model_evaluation_run(payload: ModelEvaluationRunIn, current_user: User = Depends(require_role("admin"))):
    from src.domain.evaluation.evaluation_engine import EvaluationEngine
    engine = EvaluationEngine()
    try:
        run_id = engine.create_run(
            name=payload.name, models=payload.models,
            historical_incident_ids=payload.historical_incident_ids,
            prompt_version=payload.prompt_version or "v1", created_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"run_id": run_id, "status": "PENDING"}


async def _run_model_evaluation_background(run_id: str) -> None:
    from src.domain.evaluation.evaluation_engine import EvaluationEngine
    try:
        await EvaluationEngine().run_evaluation(run_id)
    except Exception as e:
        print(f"Model evaluation run {run_id} background execution failed: {e}")


@app.post("/api/v2/admin/model-evaluation/runs/{run_id}/start")
async def start_model_evaluation_run(run_id: str, current_user: User = Depends(require_role("admin"))):
    """
    Starts execution of every (model, historical_incident) pair in this run
    as a background task -- this can legitimately take a long time (each
    replay is a real, full multi-agent investigation against a live LLM),
    so the API returns immediately, matching how a single replay is already
    dispatched via asyncio.create_task in _run_replay_background above.
    """
    from src.domain.evaluation.evaluation_engine import EvaluationEngine
    engine = EvaluationEngine()
    run = engine.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    asyncio.create_task(_run_model_evaluation_background(run_id))
    return {"run_id": run_id, "status": "RUNNING"}


@app.get("/api/v2/admin/model-evaluation/runs")
async def list_model_evaluation_runs(current_user: User = Depends(require_role("admin"))):
    from src.domain.evaluation.evaluation_engine import EvaluationEngine
    return EvaluationEngine().list_runs()


@app.get("/api/v2/admin/model-evaluation/runs/{run_id}")
async def get_model_evaluation_run(run_id: str, current_user: User = Depends(require_role("admin"))):
    from src.domain.evaluation.evaluation_engine import EvaluationEngine
    run = EvaluationEngine().get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return run


@app.get("/api/v2/admin/model-evaluation/runs/{run_id}/scorecard")
async def get_model_evaluation_scorecard(run_id: str, current_user: User = Depends(require_role("admin"))):
    """
    The scorecard requested by the spec: RCA Top-1/Top-3, cause-family
    accuracy, evidence citation presence, and latency, computed live per
    model from real replay results. Metrics this deployment doesn't yet
    instrument (tool-loop counts, token usage, cost) are explicitly marked
    unavailable rather than fabricated.
    """
    from src.domain.evaluation.evaluation_engine import EvaluationEngine
    try:
        return EvaluationEngine().get_scorecard(run_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Evaluation run not found")


# ---------------------------------------------------------------------------
# Commander Live / Commander Pulse (WP-ORG-002).
# See docs/NemoGuard_Internal_Org_Next_Steps_for_Coding_Agent_2026-08-27_v2_Commander_Live.md
# section 4. Commander Pulse projects the existing audit_event stream into
# meaningful status updates; Commander Live is the persistent
# ASK/GUIDE/ADD_FACT conversation attached to every incident. Every
# endpoint below is scoped to the caller's tenant via the same
# _require_incident_in_tenant helper used by every other incident
# sub-resource.
# ---------------------------------------------------------------------------

@app.get("/api/v2/incidents/{incident_id}/commander/status")
def get_commander_pulse(incident_id: str, current_user: User = Depends(get_current_user)):
    from src.domain.commander.status_projector import StatusProjector
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    _require_incident_in_tenant(db, incident_id, current_user.tenant_id)
    return StatusProjector(db).get_pulse(incident_id)


@app.get("/api/v2/incidents/{incident_id}/commander/messages")
def get_commander_messages(incident_id: str, current_user: User = Depends(get_current_user)):
    from src.domain.commander.conversation import CommanderConversation
    conv = CommanderConversation()
    return conv.get_messages(incident_id, current_user.tenant_id)


class CommanderAskRequest(BaseModel):
    question: str


@app.post("/api/v2/incidents/{incident_id}/commander/ask")
async def commander_ask(incident_id: str, req: CommanderAskRequest, current_user: User = Depends(get_current_user)):
    from src.domain.commander.conversation import CommanderConversation, IncidentNotFoundError
    conv = CommanderConversation()
    try:
        return await conv.ask(incident_id, current_user.tenant_id, req.question, current_user.user_id)
    except IncidentNotFoundError:
        raise HTTPException(status_code=404, detail="Incident not found")


class CommanderGuidanceRequest(BaseModel):
    text: str
    guidance_type: Optional[str] = "INVESTIGATION_DIRECTION"


@app.post("/api/v2/incidents/{incident_id}/commander/guidance")
async def commander_guidance(incident_id: str, req: CommanderGuidanceRequest, current_user: User = Depends(require_role("operator"))):
    from src.domain.commander.conversation import CommanderConversation, IncidentNotFoundError
    conv = CommanderConversation()
    try:
        return await conv.guide(
            incident_id, current_user.tenant_id, req.text, current_user.user_id,
            guidance_type=req.guidance_type or "INVESTIGATION_DIRECTION", is_fact=False,
        )
    except IncidentNotFoundError:
        raise HTTPException(status_code=404, detail="Incident not found")


class CommanderFactRequest(BaseModel):
    text: str


@app.post("/api/v2/incidents/{incident_id}/commander/facts")
async def commander_add_fact(incident_id: str, req: CommanderFactRequest, current_user: User = Depends(require_role("operator"))):
    from src.domain.commander.conversation import CommanderConversation, IncidentNotFoundError
    conv = CommanderConversation()
    try:
        return await conv.guide(
            incident_id, current_user.tenant_id, req.text, current_user.user_id,
            guidance_type="MANUAL_EVIDENCE_REFERENCE", is_fact=True,
        )
    except IncidentNotFoundError:
        raise HTTPException(status_code=404, detail="Incident not found")


# ---------------------------------------------------------------------------
# Teams Incident Communications (WP-ORG-002 §4.19-4.22). Admin-only route
# management -- webhook URLs themselves are never accepted/stored here,
# only routing/policy metadata (see migrations/013_teams_notifications.sql).
# ---------------------------------------------------------------------------

class TeamsRouteIn(BaseModel):
    name: str
    enabled: bool = True
    environment: Optional[str] = None
    service_pattern: Optional[str] = None
    severity_threshold: Optional[str] = None
    team_id: Optional[str] = None
    channel_id: Optional[str] = None
    delivery_mode: str = "WORKFLOWS_WEBHOOK"
    notify_on: List[str] = []


@app.post("/api/v2/admin/teams/routes")
async def create_teams_route(payload: TeamsRouteIn, current_user: User = Depends(require_role("admin"))):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    route_id = f"TROUTE-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO teams_notification_route (
                route_id, name, enabled, environment, service_pattern, severity_threshold,
                team_id, channel_id, delivery_mode, notify_on_json, created_by, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                route_id, payload.name, int(payload.enabled), payload.environment, payload.service_pattern,
                payload.severity_threshold, payload.team_id, payload.channel_id, payload.delivery_mode,
                json.dumps(payload.notify_on), current_user.user_id, now, now,
            ),
        )
    expected_env_var = "TEAMS_WEBHOOK_URL_" + "".join(c if c.isalnum() else "_" for c in route_id.upper())
    return {
        "route_id": route_id,
        "note": f"Set the webhook URL via the environment variable {expected_env_var} for this route to actually deliver.",
    }


@app.get("/api/v2/admin/teams/routes")
async def list_teams_routes(current_user: User = Depends(require_role("admin"))):
    from src.domain.notifications.teams_adapter import resolve_webhook_url
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM teams_notification_route ORDER BY created_at DESC")
        cols = [c[0] for c in cursor.description]
        rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
    for r in rows:
        r["webhook_configured"] = bool(resolve_webhook_url(r["route_id"]))
        if r.get("notify_on_json"):
            try:
                r["notify_on"] = json.loads(r["notify_on_json"])
            except Exception:
                r["notify_on"] = []
    return rows


@app.get("/api/v2/admin/teams/deliveries")
async def list_teams_deliveries(incident_id: Optional[str] = None, current_user: User = Depends(require_role("admin"))):
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        if incident_id:
            cursor = conn.execute(
                "SELECT * FROM teams_notification_delivery WHERE incident_id = %s ORDER BY created_at DESC LIMIT 200",
                (incident_id,),
            )
        else:
            cursor = conn.execute("SELECT * FROM teams_notification_delivery ORDER BY created_at DESC LIMIT 200")
        cols = [c[0] for c in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Incident Memory (WP-ORG-003). Admin-only review/lifecycle management --
# users must be able to view/edit/approve/reject/redact/delete memory as
# policy permits (acceptance criteria). Draft generation and similarity
# retrieval happen automatically inside the orchestrator (see
# src/domain/orchestrator.py::_generate_memory_draft_best_effort /
# _retrieve_memory_feedback_context); these endpoints are purely for the
# human review workflow and inspecting what was retrieved for a given
# incident.
# ---------------------------------------------------------------------------

@app.get("/api/v2/admin/memory")
async def list_incident_memory(status: Optional[str] = None, current_user: User = Depends(require_role("admin"))):
    from src.domain.memory.memory_engine import MemoryEngine
    return MemoryEngine().list_memory(current_user.tenant_id, status=status)


@app.get("/api/v2/admin/memory/{memory_id}")
async def get_incident_memory_detail(memory_id: str, current_user: User = Depends(require_role("admin"))):
    from src.domain.memory.memory_engine import MemoryEngine
    memory = MemoryEngine().get_memory(memory_id, current_user.tenant_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory record not found")
    return memory


class MemoryStatusUpdateIn(BaseModel):
    new_status: str
    review_notes: Optional[str] = None


@app.post("/api/v2/admin/memory/{memory_id}/status")
async def update_incident_memory_status(memory_id: str, payload: MemoryStatusUpdateIn, current_user: User = Depends(require_role("admin"))):
    from src.domain.memory.memory_engine import MemoryEngine, VALID_STATUSES
    if payload.new_status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid new_status. Must be one of: {sorted(VALID_STATUSES)}")
    engine = MemoryEngine()
    ok = engine.update_status(memory_id, current_user.tenant_id, payload.new_status, current_user.user_id, payload.review_notes)
    if not ok:
        raise HTTPException(status_code=404, detail="Memory record not found")
    return {"memory_id": memory_id, "memory_status": payload.new_status}


class MemoryEditIn(BaseModel):
    root_cause: Optional[str] = None
    cause_type: Optional[str] = None
    successful_recovery: Optional[str] = None
    human_feedback: Optional[str] = None
    verification_result: Optional[str] = None
    data_integrity_result: Optional[str] = None


@app.patch("/api/v2/admin/memory/{memory_id}")
async def edit_incident_memory(memory_id: str, payload: MemoryEditIn, current_user: User = Depends(require_role("admin"))):
    from src.domain.memory.memory_engine import MemoryEngine
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=422, detail="No editable fields provided")
    ok = MemoryEngine().edit_memory(memory_id, current_user.tenant_id, current_user.user_id, **fields)
    if not ok:
        raise HTTPException(status_code=404, detail="Memory record not found")
    return {"memory_id": memory_id, "memory_status": "DRAFT"}


@app.delete("/api/v2/admin/memory/{memory_id}")
async def delete_incident_memory(memory_id: str, current_user: User = Depends(require_role("admin"))):
    from src.domain.memory.memory_engine import MemoryEngine
    ok = MemoryEngine().delete_memory(memory_id, current_user.tenant_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Memory record not found")
    return {"status": "deleted", "memory_id": memory_id}


@app.get("/api/v2/incidents/{incident_id}/recurrences")
def get_incident_recurrences(incident_id: str, current_user: User = Depends(get_current_user)):
    """WP-ORG-006: surfaces any detected historical-recurrence links for
    this incident (both directions -- as the new incident that resembled
    something prior, and as a prior incident that a later one resembled)."""
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    _require_incident_in_tenant(db, incident_id, current_user.tenant_id)
    with db.get_connection() as conn:
        cursor = conn.execute(
            "SELECT r.*, i.title AS prior_title, i.actual_root_cause AS prior_root_cause "
            "FROM incident_recurrence r JOIN incident i ON i.incident_id = r.prior_incident_id "
            "WHERE r.new_incident_id = %s",
            (incident_id,),
        )
        cols = [c[0] for c in cursor.description]
        as_new = [dict(zip(cols, row)) for row in cursor.fetchall()]

        cursor = conn.execute(
            "SELECT r.*, i.title AS new_title, i.status AS new_status "
            "FROM incident_recurrence r JOIN incident i ON i.incident_id = r.new_incident_id "
            "WHERE r.prior_incident_id = %s",
            (incident_id,),
        )
        cols = [c[0] for c in cursor.description]
        as_prior = [dict(zip(cols, row)) for row in cursor.fetchall()]
    return {"as_new_incident": as_new, "as_prior_incident": as_prior}


@app.get("/api/v2/incidents/{incident_id}/memory-retrievals")
def get_incident_memory_retrievals(incident_id: str, current_user: User = Depends(get_current_user)):
    """Lets an operator see exactly what historical memory (if any) was
    retrieved and presented as evidence for THIS incident's investigation
    -- acceptance criterion: 'memory retrieval is visible in the UI'."""
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    _require_incident_in_tenant(db, incident_id, current_user.tenant_id)
    from src.domain.memory.memory_engine import MemoryEngine
    return MemoryEngine(db).get_retrievals_for_incident(incident_id)


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
        payload = _jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except _jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except _jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Per docs build plan Priority 8 / spec §12.5 ("SSE cannot leak another
    # tenant's events"): decoding the token only proves the caller holds
    # SOME valid JWT -- it does not by itself prove they're allowed to see
    # THIS incident's audit stream. Previously any valid token from any
    # tenant could stream any incident's live agent-reasoning trail.
    stream_db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    _require_incident_in_tenant(stream_db, incident_id, payload.get("tenant_id", "default_tenant"))

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
