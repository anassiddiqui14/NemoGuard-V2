import os
import uuid
import json
import time
import random
import httpx
from datetime import datetime, timezone
import psycopg2
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="NemoGuard Application Simulator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db")

import openai
from openai import AsyncOpenAI
import asyncio

class PromptRequest(BaseModel):
    prompt: str

async def generate_and_inject_ai(prompt: str):
    yield "status: Initializing run context...\n"
    run_id = f"RUN-SIM-{uuid.uuid4().hex[:6].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    
    generate_noise_logs(run_id, 150)
    
    yield "status: Generating AI mock incidents from NVIDIA Nemotron...\n"
    
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        yield "status: ERROR - NVIDIA_API_KEY is not configured on the simulator service.\n"
        return
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://integrate.api.nvidia.com/v1"
    )
    
    system_prompt = '''You are a mock incident generator for NemoGuard.
The user will describe a scenario. Generate a strictly formatted JSON response containing mock data.
Format:
{
  "failure_logs": [
    {"level": "INFO|WARN|ERROR", "component": "service_name", "message": "log message"}
  ],
  "webhook_payloads": [
    {
      "source": "Datadog|Airflow|PagerDuty",
      "type": "Monitor Alert",
      "monitor_name": "Alert title",
      "message": "Alert description",
      "tags": ["service:service_name", "env:prod", "severity:critical"]
    }
  ],
  "business_assets": [
    {
      "asset_name": "Name of downstream dashboard/product impacted",
      "asset_type": "Dashboard|Data Product|API",
      "owner": "Team Name",
      "sla_minutes": 60,
      "criticality": 1,
      "depends_on_service": "service_name"
    }
  ],
  "runbooks": [
    {
      "service_name": "service_name",
      "title": "Standard Operating Procedure for service_name",
      "prerequisites_json": "[]",
      "steps": ["Step 1...", "Step 2..."],
      "verification_json": "[]",
      "rollback_json": "[]"
    }
  ]
}
Generate 5-10 failure_logs, 2-4 webhook_payloads, 2-4 business_assets, and 1-2 runbooks.
Ensure that the tags in webhook_payloads include service:service_name that matches the component in failure_logs, depends_on_service in business_assets, and service_name in runbooks. This is critical for agents to correlate everything.
'''
    try:
        completion = await client.chat.completions.create(
            model="nvidia/nemotron-3-super-120b-a12b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        result = json.loads(completion.choices[0].message.content)
        failure_logs = result.get("failure_logs", [])
        webhook_payloads = result.get("webhook_payloads", [])
        business_assets = result.get("business_assets", [])
        runbooks = result.get("runbooks", [])
    except Exception as e:
        yield f"status: LLM generation failed: {e}\n"
        return
        
    yield f"status: Generated {len(webhook_payloads)} alerts, {len(failure_logs)} logs, {len(business_assets)} assets, and {len(runbooks)} runbooks. Injecting...\n"
        
    for payload in webhook_payloads:
        payload["run_id"] = run_id
        
    logs_to_insert = []
    for log in failure_logs:
        logs_to_insert.append((f"LOG-{uuid.uuid4().hex[:6]}", run_id, now, log.get("level", "ERROR"), log.get("component", "unknown"), None, log.get("message", "error")))
        
    assets_to_insert = []
    asset_dependencies_to_insert = []
    for idx, asset in enumerate(business_assets):
        asset_id = f"AST-{uuid.uuid4().hex[:6]}"
        job_id = f"JOB_{asset.get('depends_on_service', 'SIMULATOR_JOB').upper()}"
        assets_to_insert.append((asset_id, asset.get("asset_name"), asset.get("asset_type"), asset.get("owner"), asset.get("sla_minutes", 60), asset.get("criticality", 1), ""))
        asset_dependencies_to_insert.append((asset_id, job_id))

    runbooks_to_insert = []
    for idx, rb in enumerate(runbooks):
        rb_id = f"RBK-{uuid.uuid4().hex[:6]}"
        job_name = f"JOB_{rb.get('service_name', 'SIMULATOR_JOB').upper()}"
        title = rb.get("title", f"Runbook for {job_name}")
        steps_str = "\n".join([f"{i+1}. {s}" for i, s in enumerate(rb.get("steps", []))])
        runbooks_to_insert.append((
            1, "default", "default", rb_id, title, "synthetic", "active", "Ops", "none",
            rb.get("prerequisites_json", "[]"), rb.get("verification_json", "[]"), rb.get("rollback_json", "[]"),
            now, "default", now
        ))
        
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cursor:
            # We must create jobs for all the dependencies generated so foreign keys work
            unique_jobs = set([j for _, j in asset_dependencies_to_insert])
            unique_jobs.add("SIMULATOR_JOB")
            for jb in unique_jobs:
                cursor.execute('''
                    INSERT INTO job (job_id, job_name, platform, domain, stage, schedule, criticality, default_duration_sec, owner_team, retry_policy, active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (job_id) DO NOTHING
                ''', (jb, jb, 'Simulator', 'Test', 'Ingest', '@daily', 1, 60, 'DataOps', 'none', True))

            cursor.execute('''
                INSERT INTO execution (run_id, job_id, scheduled_ts, start_ts, end_ts, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id) DO NOTHING
            ''', (run_id, 'SIMULATOR_JOB', now, now, now, 'failed'))
            
            cursor.executemany('''
                INSERT INTO log_event (log_id, run_id, timestamp, level, component, error_code, message)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', logs_to_insert)

            cursor.executemany('''
                INSERT INTO business_asset (asset_id, asset_name, asset_type, owner, sla_minutes, criticality, communication_template)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (asset_id) DO NOTHING
            ''', assets_to_insert)

            cursor.executemany('''
                INSERT INTO asset_dependency (asset_id, job_id)
                VALUES (%s, %s)
                ON CONFLICT (asset_id, job_id) DO NOTHING
            ''', asset_dependencies_to_insert)

            cursor.executemany('''
                INSERT INTO runbook (version, workspace_id, environment_id, runbook_id, title, incident_type, status, owner_team, approval_policy, prerequisites_json, verification_json, rollback_json, created_at, tenant_id, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (runbook_id) DO NOTHING
            ''', runbooks_to_insert)

        conn.commit()
        
    # Fire webhooks
    yield "status: Firing webhooks to NemoGuard Commander...\n"
    async with httpx.AsyncClient() as client:
        for payload in webhook_payloads:
            try:
                response = await client.post("http://api:8000/api/v2/ingest/webhook", json=payload, timeout=60.0)
                yield f"status: Sent webhook to NemoGuard: {response.status_code}\n"
                await asyncio.sleep(1)
            except Exception as e:
                yield f"status: Failed to send webhook to NemoGuard: {str(e)}\n"
                
    yield "status: Successfully injected AI Incident into NemoGuard!\n"

@app.post("/trigger/ai")
async def trigger_scenario_ai(req: PromptRequest):
    return StreamingResponse(generate_and_inject_ai(req.prompt), media_type="text/event-stream")

class ScenarioRequest(BaseModel):
    scenario_type: str = "SCHEMA_REGRESSION"
    
def generate_noise_logs(run_id: str, count: int = 150):
    now = datetime.now(timezone.utc).isoformat()
    noise_components = ["auth_service", "kafka_ingest", "api_gateway", "session_manager", "health_checker"]
    noise_messages = [
        "Heartbeat ping successful.",
        "Session refreshed for user {uid}.",
        "Garbage collection completed in {ms}ms.",
        "Checking configuration drift...",
        "Connection pool size: 45/100",
        "Emitting telemetry batch.",
        "Rate limit check passed.",
        "Flushing metrics buffer."
    ]
    logs = []
    for _ in range(count):
        comp = random.choice(noise_components)
        msg = random.choice(noise_messages).replace("{uid}", str(random.randint(1000, 9999))).replace("{ms}", str(random.randint(10, 300)))
        logs.append((f"LOG-{uuid.uuid4().hex[:6]}", run_id, now, "INFO", comp, None, msg))
    
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO job (job_id, job_name, platform, domain, stage, schedule, criticality, default_duration_sec, owner_team, retry_policy, active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (job_id) DO NOTHING
            """, ('SIMULATOR_JOB', 'Simulator Job', 'Simulator', 'Test', 'Ingest', '@daily', 1, 60, 'DataOps', 'none', True))
            cursor.execute("""
                INSERT INTO execution (run_id, job_id, scheduled_ts, start_ts, end_ts, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id) DO NOTHING
            """, (run_id, 'SIMULATOR_JOB', now, now, now, 'failed'))

            cursor.executemany("""
                INSERT INTO log_event (log_id, run_id, timestamp, level, component, error_code, message)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, logs)
        conn.commit()

def simulate_failure(scenario_type: str):
    run_id = f"RUN-SIM-{uuid.uuid4().hex[:6].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    
    # 1. Generate normal operations noise
    generate_noise_logs(run_id, 150)
    
    # 2. Generate specific failure logs
    failure_logs = []
    webhook_payload = {}
    
    if scenario_type == "SCHEMA_REGRESSION":
        failure_logs = [
            ("INFO", "customer_profile", f"Starting job {run_id} to consume CDC stream"),
            ("WARN", "kafka_ingest", "Consumer lag increasing beyond threshold on topic user_updates"),
            ("ERROR", "customer_profile", "ValidationException: Missing required column 'last_login_ip' in schema version v4.2"),
            ("ERROR", "customer_profile", "Task failed: Max retries exceeded for schema validation error"),
            ("ERROR", "marketing_sync_job", "Dependency customer_profile failed, aborting downstream sync.")
        ]
        webhook_payloads = [
            {
                "source": "Datadog",
                "type": "Monitor Alert",
                "monitor_name": "[CRITICAL] High error rate on customer_profile schema validation",
                "message": "The customer_profile service is throwing a high number of ValidationExceptions due to schema mismatch (v4.2 missing 'last_login_ip').",
                "tags": ["service:customer_profile", "env:prod", "severity:critical"],
                "run_id": run_id
            },
            {
                "source": "Airflow",
                "type": "Job Failure",
                "monitor_name": "marketing_sync_job failed",
                "message": "The marketing_sync_job failed because upstream dependency customer_profile failed to complete.",
                "tags": ["service:marketing_sync_job", "env:prod", "severity:high"],
                "run_id": run_id
            },
            {
                "source": "PagerDuty",
                "type": "Customer Escalation",
                "monitor_name": "Loyalty Executive Dashboard Outdated",
                "message": "Marketing team reports the Loyalty Executive Dashboard has not updated in the last hour.",
                "tags": ["service:Loyalty Executive Dashboard", "env:prod", "severity:high"],
                "run_id": run_id
            }
        ]
    elif scenario_type == "OOM_CRASH":
        failure_logs = [
            ("INFO", "JOB_AWS_EXTRACT_RESERVATION", f"Initializing Spark context for run {run_id}"),
            ("INFO", "aws_rds_main", "Connection established from executor 1"),
            ("WARN", "JOB_AWS_EXTRACT_RESERVATION", "Memory usage at 85% of allocated heap space"),
            ("ERROR", "JOB_AWS_EXTRACT_RESERVATION", "java.lang.OutOfMemoryError: Java heap space"),
            ("ERROR", "Reservation Analytics Mart", "Upstream job failed, SLA breached.")
        ]
        webhook_payloads = [
            {
                "source": "PagerDuty",
                "type": "Incident Trigger",
                "service": "AWS_EXTRACT",
                "title": "Spark Job Failed - OutOfMemoryError",
                "description": "The nightly AWS extraction job crashed due to Java heap space exhaustion.",
                "urgency": "high",
                "run_id": run_id
            }
        ]
    elif scenario_type == "CASCADING_FAILURE":
        failure_logs = [
            ("INFO", "auth_db", "Starting routine compaction on auth_tokens table."),
            ("WARN", "auth_db", "Transaction blocked: deadlock detected on auth_tokens."),
            ("ERROR", "auth_db", "FATAL: Deadlock timeout reached. Aborting transactions."),
            ("ERROR", "auth_api", "Connection timeout to auth_db after 5000ms. Retrying..."),
            ("ERROR", "auth_api", "FATAL: auth_db connection pool exhausted."),
            ("ERROR", "checkout_service", "HTTP 500 from auth_api during token validation."),
            ("ERROR", "payment_gateway", "Failed to authorize charge: missing valid auth token."),
            ("ERROR", "reporting_dashboard", "Data lag detected: checkout_service metrics stopped reporting.")
        ]
        webhook_payloads = [
            {
                "source": "Datadog",
                "type": "Monitor Alert",
                "monitor_name": "[CRITICAL] auth_db Deadlock Rate Spike",
                "message": "auth_db is experiencing high rate of deadlocks on auth_tokens table.",
                "tags": ["service:auth_db", "env:prod", "severity:critical"],
                "run_id": run_id
            },
            {
                "source": "Datadog",
                "type": "Monitor Alert",
                "monitor_name": "[HIGH] auth_api p99 Latency Breach",
                "message": "auth_api p99 latency is over 5000ms due to database connection exhaustion.",
                "tags": ["service:auth_api", "env:prod", "severity:high"],
                "run_id": run_id
            },
            {
                "source": "PagerDuty",
                "type": "Incident Trigger",
                "service": "checkout_service",
                "title": "Checkout Service Error Rate High",
                "description": "Checkout service is returning HTTP 500s during customer transactions.",
                "urgency": "high",
                "run_id": run_id
            },
            {
                "source": "Sentry",
                "type": "Exception Alert",
                "monitor_name": "payment_gateway AuthorizationFailure",
                "message": "payment_gateway failed to authorize due to invalid tokens.",
                "tags": ["service:payment_gateway", "env:prod", "severity:high"],
                "run_id": run_id
            },
            {
                "source": "Datadog",
                "type": "Monitor Alert",
                "monitor_name": "[WARNING] reporting_dashboard Data Lag",
                "message": "Sales metrics are lagging by over 5 minutes.",
                "tags": ["service:reporting_dashboard", "env:prod", "severity:warning"],
                "run_id": run_id
            }
        ]
    else:
        # Generic
        failure_logs = [
            ("ERROR", "unknown_service", "Unknown generic failure occurred.")
        ]
        webhook_payloads = [
            {
                "source": "Custom",
                "type": "Generic Alert",
                "message": f"A failure of type {scenario_type} occurred.",
                "run_id": run_id
            }
        ]
        
    logs_to_insert = []
    for level, component, msg in failure_logs:
        logs_to_insert.append((f"LOG-{uuid.uuid4().hex[:6]}", run_id, now, level, component, None, msg))
        
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO job (job_id, job_name, platform, domain, stage, schedule, criticality, default_duration_sec, owner_team, retry_policy, active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (job_id) DO NOTHING
            """, ('SIMULATOR_JOB', 'Simulator Job', 'Simulator', 'Test', 'Ingest', '@daily', 1, 60, 'DataOps', 'none', True))
            
            if scenario_type == "CASCADING_FAILURE":
                # Ensure the assets are in the CMDB
                cmdb_assets = [
                    ('auth_db', 'auth_db', 'Database', 'Auth', 'Prod', '@always', 1, 0, 'DBA', 'none', True),
                    ('auth_api', 'auth_api', 'Service', 'Auth', 'Prod', '@always', 1, 0, 'Backend', 'none', True),
                    ('checkout_service', 'checkout_service', 'Service', 'Checkout', 'Prod', '@always', 1, 0, 'Backend', 'none', True),
                    ('payment_gateway', 'payment_gateway', 'Service', 'Checkout', 'Prod', '@always', 1, 0, 'Payments', 'none', True),
                    ('reporting_dashboard', 'reporting_dashboard', 'Dashboard', 'Analytics', 'Prod', '@always', 1, 0, 'Data', 'none', True)
                ]
                cursor.executemany("""
                    INSERT INTO job (job_id, job_name, platform, domain, stage, schedule, criticality, default_duration_sec, owner_team, retry_policy, active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (job_id) DO NOTHING
                """, cmdb_assets)
                
                # Insert dependencies
                deps = [
                    ('EDGE-1', 'auth_db', 'auth_api', 'upstream', 0, True),
                    ('EDGE-2', 'auth_api', 'checkout_service', 'upstream', 0, True),
                    ('EDGE-3', 'checkout_service', 'payment_gateway', 'upstream', 0, True),
                    ('EDGE-4', 'checkout_service', 'reporting_dashboard', 'data', 0, True)
                ]
                cursor.executemany("""
                    INSERT INTO dependency (edge_id, parent_job_id, child_job_id, dependency_type, max_lag_min, required)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, deps)
                
                # Insert runbook
                cursor.execute("""
                    INSERT INTO runbook (runbook_id, version, status, owner_team, approval_policy, created_at, updated_at, title, incident_type, prerequisites_json, verification_json, rollback_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (runbook_id) DO NOTHING
                """, ('RB-AUTH-DB-001', 1, 'active', 'DBA', 'manual', now, now, 'Standard Operating Procedure for auth_db Deadlocks', 'Database Deadlock', '["Access to auth_db primary instance"]', '["Check active locks view"]', '["None"]'))
                cursor.execute("""
                    INSERT INTO runbook_step (runbook_id, step_no, title, instruction, risk_level, requires_approval)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (runbook_id, step_no) DO NOTHING
                """, ('RB-AUTH-DB-001', 1, 'Terminate blocked queries', 'SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE wait_event_type = \'Lock\';', 'medium', 1))

            cursor.execute("""
                INSERT INTO execution (run_id, job_id, scheduled_ts, start_ts, end_ts, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id) DO NOTHING
            """, (run_id, 'SIMULATOR_JOB', now, now, now, 'failed'))
            cursor.executemany("""
                INSERT INTO log_event (log_id, run_id, timestamp, level, component, error_code, message)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, logs_to_insert)
        conn.commit()
        
    # 3. Fire the webhooks to NemoGuard
    for payload in webhook_payloads:
        try:
            response = httpx.post("http://api:8000/api/v2/ingest/webhook", json=payload, timeout=60.0)
            print(f"Sent webhook to NemoGuard: {response.status_code}")
            time.sleep(1) # small delay between alerts
        except Exception as e:
            print(f"Failed to send webhook to NemoGuard: {e}")

@app.post("/trigger")
def trigger_scenario(req: ScenarioRequest, bg: BackgroundTasks):
    bg.add_task(simulate_failure, req.scenario_type)
    return {"status": "accepted", "scenario": req.scenario_type}

@app.post("/reset")
def reset_database():
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE incident CASCADE;")
            cursor.execute("TRUNCATE TABLE alert CASCADE;")
        conn.commit()
    return {"status": "success", "message": "All incidents and alerts cleared"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
