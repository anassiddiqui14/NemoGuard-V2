import os
import sys
import uuid
import json
import time
import random
import threading
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

# --- Real-AWS "Scenario Cockpit" lab integration -----------------------
# Bundled into this image at build time (see Dockerfile.simulator) so the
# cockpit's "real AWS lab" scenarios can reuse localstack_lab's exact
# resource-naming conventions and boto3 client factory instead of a second,
# inevitably-drifting copy of that logic.
sys.path.insert(0, os.path.dirname(__file__))
try:
    from localstack_lab.aws_clients import client as aws_client  # type: ignore
    LOCALSTACK_LAB_IMPORTABLE = True
except Exception:
    LOCALSTACK_LAB_IMPORTABLE = False

LAB_BUCKET_NAME = "nemoguard-lab-data"
LAB_FUNCTIONS = {
    "ingest_job": "nemoguard-ingest-job",
    "order_events_job": "nemoguard-order-events-job",
    "notification_job": "nemoguard-notification-job",
}
LAB_ALERTS_QUEUE_NAME = "nemoguard-lab-alerts-queue"
LAB_STATE_MACHINE_NAME = "nemoguard-daily-pipeline"
NEMOGUARD_API_BASE = os.environ.get("NEMOGUARD_API_BASE", "http://api:8000")

FUNCTION_NAME_TO_JOB_ID = {
    "nemoguard-ingest-job": "LOCALSTACK_INGEST_JOB",
    "nemoguard-order-events-job": "LOCALSTACK_ORDER_EVENTS_JOB",
    "nemoguard-notification-job": "LOCALSTACK_NOTIFICATION_JOB",
}


def _lab_forwarder_loop():
    """Background thread (started once, at process startup) that continually
    polls the REAL SQS queue subscribed to the lab's CloudWatch->SNS alarm
    pipeline and forwards each notification into NemoGuard's existing
    webhook endpoint -- functionally identical to localstack_lab/forwarder.py,
    just running in-process inside this container so the cockpit doesn't
    require a human to separately remember to start (and keep running) a
    second terminal process for the forwarder every time the lab is used.
    """
    if not LOCALSTACK_LAB_IMPORTABLE:
        print("[lab-forwarder] localstack_lab not importable; forwarder thread not starting.")
        return
    try:
        sqs = aws_client("sqs")
        queue_url = sqs.get_queue_url(QueueName=LAB_ALERTS_QUEUE_NAME)["QueueUrl"]
    except Exception as e:
        print(f"[lab-forwarder] queue not available yet ({e}); forwarder thread not starting. "
              f"Provision the lab (localstack_lab/provision.py) and restart the simulator to enable it.")
        return

    print(f"[lab-forwarder] started. Polling {LAB_ALERTS_QUEUE_NAME} -> {NEMOGUARD_API_BASE}/api/v2/ingest/webhook")
    while True:
        try:
            resp = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=10)
            for msg in resp.get("Messages", []):
                try:
                    sns_envelope = json.loads(msg["Body"])
                    alarm_body = json.loads(sns_envelope.get("Message", "{}"))
                    payload = _cloudwatch_alarm_to_webhook_payload(alarm_body)
                    r = httpx.post(f"{NEMOGUARD_API_BASE}/api/v2/ingest/webhook", json=payload, timeout=30.0)
                    print(f"[lab-forwarder] forwarded alarm '{payload.get('alarm_name')}': HTTP {r.status_code}")
                except Exception as e:
                    print(f"[lab-forwarder] failed to process message: {e}")
                finally:
                    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"])
        except Exception as e:
            print(f"[lab-forwarder] poll error: {e}")
            time.sleep(5)


def _most_recent_failed_run_id(job_id: str):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT run_id FROM execution WHERE job_id = %s AND status = 'failed' "
                "ORDER BY end_ts DESC LIMIT 1",
                (job_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None
    except Exception:
        return None


def _cloudwatch_alarm_to_webhook_payload(alarm_body: dict) -> dict:
    function_name = None
    for dim in alarm_body.get("Trigger", {}).get("Dimensions", []):
        if dim.get("name") == "FunctionName":
            function_name = dim.get("value")
    job_id = FUNCTION_NAME_TO_JOB_ID.get(function_name, "LOCALSTACK_INGEST_JOB")
    real_run_id = _most_recent_failed_run_id(job_id)
    run_id = real_run_id or f"RUN-LOCALSTACK-{int(time.time())}"
    return {
        "source": "CloudWatch (LocalStack)",
        "type": "Alarm",
        "monitor_name": alarm_body.get("AlarmName", "Unknown Alarm"),
        "message": alarm_body.get(
            "NewStateReason",
            f"CloudWatch alarm {alarm_body.get('AlarmName')} entered ALARM state.",
        ),
        "tags": [
            f"service:{function_name or 'nemoguard-ingest-job'}",
            "env:localstack-lab",
            "severity:critical",
        ],
        "run_id": run_id,
        "alarm_name": alarm_body.get("AlarmName"),
        "new_state": alarm_body.get("NewStateValue"),
        "region": alarm_body.get("Region"),
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }


_lab_forwarder_thread_started = False


@app.on_event("startup")
def _start_lab_forwarder_once():
    global _lab_forwarder_thread_started
    if _lab_forwarder_thread_started:
        return
    _lab_forwarder_thread_started = True
    t = threading.Thread(target=_lab_forwarder_loop, daemon=True)
    t.start()


class LabTriggerRequest(BaseModel):
    scenario: str


def _lab_check_available() -> tuple[bool, str]:
    if not LOCALSTACK_LAB_IMPORTABLE:
        return False, "localstack_lab package not importable in this container."
    try:
        lam = aws_client("lambda")
        names = {f["FunctionName"] for f in lam.list_functions().get("Functions", [])}
        missing = set(LAB_FUNCTIONS.values()) - names
        if missing:
            return False, f"LocalStack reachable but not provisioned. Missing functions: {sorted(missing)}. Run localstack_lab/provision.py."
        return True, "ready"
    except Exception as e:
        return False, f"LocalStack unreachable: {e}"


@app.get("/lab/status")
def lab_status():
    available, detail = _lab_check_available()
    return {
        "available": available,
        "detail": detail,
        "functions": LAB_FUNCTIONS,
        "forwarder_running": _lab_forwarder_thread_started,
    }


def _lab_invoke(function_name: str, payload: dict) -> dict:
    lam = aws_client("lambda")
    resp = lam.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode(),
    )
    raw_payload = resp["Payload"].read().decode()
    return {
        "status_code": resp.get("StatusCode"),
        "function_error": resp.get("FunctionError"),
        "payload": raw_payload,
    }


_INGEST_SCENARIOS = {
    "schema_drift": {"user_id": "USR-{uid}"},
    "oom_crash": {"user_id": "USR-{uid}", "last_login_ip": "10.0.0.1", "simulate_oom": True},
    "db_outage": {"user_id": "USR-{uid}", "last_login_ip": "10.0.0.1", "simulate_db_outage": True},
    "healthy": {"user_id": "USR-{uid}", "last_login_ip": "10.0.0.1"},
}


@app.post("/lab/trigger/ingest")
def lab_trigger_ingest(req: LabTriggerRequest):
    """Real S3->Lambda->Postgres failure against nemoguard-ingest-job -- see
    localstack_lab/break_scenario.py (this mirrors that script's logic so it
    can be triggered directly from the cockpit's HTTP API instead of a
    separate CLI invocation)."""
    available, detail = _lab_check_available()
    if not available:
        raise HTTPException(status_code=503, detail=detail)
    if req.scenario not in _INGEST_SCENARIOS:
        raise HTTPException(status_code=400, detail=f"Unknown scenario. Choose from: {list(_INGEST_SCENARIOS.keys())}")

    uid = uuid.uuid4().hex[:6]
    run_id = f"RUN-LOCALSTACK-{req.scenario}-{uid}"
    key = f"customer_profile/{run_id}.json"
    record = json.loads(json.dumps(_INGEST_SCENARIOS[req.scenario]).replace("{uid}", uid))

    s3 = aws_client("s3")
    s3.put_object(Bucket=LAB_BUCKET_NAME, Key=key, Body=json.dumps(record).encode())
    result = _lab_invoke(LAB_FUNCTIONS["ingest_job"], {"bucket": LAB_BUCKET_NAME, "key": key, "run_id": run_id})
    return {"run_id": run_id, "s3_key": key, **result}


@app.post("/lab/trigger/order_events")
def lab_trigger_order_events(req: LabTriggerRequest):
    """Real Glue-style partial-write crash against nemoguard-order-events-job
    -- see localstack_lab/break_order_events_scenario.py."""
    available, detail = _lab_check_available()
    if not available:
        raise HTTPException(status_code=503, detail=detail)
    if req.scenario not in ("partial_write_crash", "healthy"):
        raise HTTPException(status_code=400, detail="Choose from: partial_write_crash, healthy")

    uid = uuid.uuid4().hex[:6]
    run_id = f"RUN-LOCALSTACK-order-events-{req.scenario}-{uid}"
    key = f"order_events/{run_id}.json"
    orders = [
        {"order_id": f"ORD-{uuid.uuid4().hex[:8]}", "event_type": "created", "amount": round(19.99 + i, 2)}
        for i in range(10)
    ]
    batch = {"orders": orders}
    if req.scenario == "partial_write_crash":
        batch["simulate_partial_write_crash"] = True
        batch["crash_after_n_rows"] = 5

    s3 = aws_client("s3")
    s3.put_object(Bucket=LAB_BUCKET_NAME, Key=key, Body=json.dumps(batch).encode())
    result = _lab_invoke(LAB_FUNCTIONS["order_events_job"], {"bucket": LAB_BUCKET_NAME, "key": key, "run_id": run_id})
    return {"run_id": run_id, "s3_key": key, "expected_row_count": len(orders), **result}


@app.post("/lab/trigger/notification")
def lab_trigger_notification(req: LabTriggerRequest):
    """Real SQS poison-pill message against nemoguard-notification-job --
    see localstack_lab/break_notification_scenario.py."""
    available, detail = _lab_check_available()
    if not available:
        raise HTTPException(status_code=503, detail=detail)
    if req.scenario not in ("poison_pill", "healthy"):
        raise HTTPException(status_code=400, detail="Choose from: poison_pill, healthy")

    uid = uuid.uuid4().hex[:6]
    run_id = f"RUN-LOCALSTACK-notification-{req.scenario}-{uid}"
    body = (
        {"simulate_poison_pill": True}
        if req.scenario == "poison_pill"
        else {"user_id": f"USR-{uid}"}
    )

    sqs = aws_client("sqs")
    queue_url = sqs.create_queue(QueueName="nemoguard-notifications-queue")["QueueUrl"]
    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(body))
    result = _lab_invoke(LAB_FUNCTIONS["notification_job"], {"run_id": run_id, "message_body": body})
    return {"run_id": run_id, **result}


_PIPELINE_SCENARIOS = {
    "ingest_step_fails": {
        "ingest_object": {"user_id": "USR-{uid}"},
        "order_events_object": {"orders": [{"order_id": "ORD-{uid}-1", "event_type": "created", "amount": 10.0}]},
    },
    "order_events_step_fails": {
        "ingest_object": {"user_id": "USR-{uid}", "last_login_ip": "10.0.0.1"},
        "order_events_object": {
            "orders": [{"order_id": f"ORD-{{uid}}-{i}", "event_type": "created", "amount": 10.0} for i in range(4)],
            "simulate_partial_write_crash": True,
            "crash_after_n_rows": 2,
        },
    },
    "healthy": {
        "ingest_object": {"user_id": "USR-{uid}", "last_login_ip": "10.0.0.1"},
        "order_events_object": {"orders": [{"order_id": "ORD-{uid}-1", "event_type": "created", "amount": 10.0}]},
    },
}


@app.post("/lab/trigger/pipeline")
def lab_trigger_pipeline(req: LabTriggerRequest):
    """Real multi-step Step Functions execution (IngestCustomerProfile ->
    ProcessOrderEvents) -- see localstack_lab/break_pipeline_scenario.py."""
    available, detail = _lab_check_available()
    if not available:
        raise HTTPException(status_code=503, detail=detail)
    if req.scenario not in _PIPELINE_SCENARIOS:
        raise HTTPException(status_code=400, detail=f"Choose from: {list(_PIPELINE_SCENARIOS.keys())}")

    uid = uuid.uuid4().hex[:6]
    ingest_key = f"customer_profile/PIPELINE-{req.scenario}-{uid}.json"
    order_events_key = f"order_events/PIPELINE-{req.scenario}-{uid}.json"
    cfg = _PIPELINE_SCENARIOS[req.scenario]

    def _sub(obj):
        return json.loads(json.dumps(obj).replace("{uid}", uid))

    ingest_object = _sub(cfg["ingest_object"])
    order_events_object = _sub(cfg["order_events_object"])

    s3 = aws_client("s3")
    s3.put_object(Bucket=LAB_BUCKET_NAME, Key=ingest_key, Body=json.dumps(ingest_object).encode())
    s3.put_object(Bucket=LAB_BUCKET_NAME, Key=order_events_key, Body=json.dumps(order_events_object).encode())

    sfn = aws_client("stepfunctions")
    state_machine_arn = None
    for sm in sfn.list_state_machines().get("stateMachines", []):
        if sm["name"] == LAB_STATE_MACHINE_NAME:
            state_machine_arn = sm["stateMachineArn"]
            break
    if not state_machine_arn:
        raise HTTPException(status_code=503, detail=f"State machine {LAB_STATE_MACHINE_NAME} not found -- run provision.py first.")

    exec_name = f"exec-{req.scenario}-{uid}"
    start_resp = sfn.start_execution(
        stateMachineArn=state_machine_arn,
        name=exec_name,
        input=json.dumps({"bucket": LAB_BUCKET_NAME, "key": ingest_key}),
    )
    execution_arn = start_resp["executionArn"]

    status = "RUNNING"
    desc = {}
    for _ in range(15):
        desc = sfn.describe_execution(executionArn=execution_arn)
        status = desc["status"]
        if status != "RUNNING":
            break
        time.sleep(1)

    return {
        "execution_arn": execution_arn,
        "status": status,
        "output": desc.get("output"),
    }


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
