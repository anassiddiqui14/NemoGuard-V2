"""Minimal local FastAPI backend backed by an empty SQLite store.

The UI receives only records created by a real ingestion or workflow; no demo
incidents, alerts, agent events, or recovery plans are seeded here.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "local.db"
app = FastAPI(title="NemoGuard Local API", version="2.0-local")


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.executescript("""
          CREATE TABLE IF NOT EXISTS incident (incident_id TEXT PRIMARY KEY, title TEXT, status TEXT, severity TEXT, detected_at TEXT, next_sla_breach_at TEXT, owner_team TEXT, primary_job_id TEXT, summary TEXT);
          CREATE TABLE IF NOT EXISTS alert (alert_id TEXT PRIMARY KEY, incident_id TEXT, severity TEXT, alert_type TEXT, source_system TEXT, message TEXT);
          CREATE TABLE IF NOT EXISTS hypothesis (hypothesis_id TEXT PRIMARY KEY, incident_id TEXT, title TEXT, confidence_score REAL);
          CREATE TABLE IF NOT EXISTS evidence (evidence_id TEXT PRIMARY KEY, incident_id TEXT, source TEXT, title TEXT, description TEXT, excerpt TEXT);
          CREATE TABLE IF NOT EXISTS impact (asset_id TEXT PRIMARY KEY, incident_id TEXT, asset_name TEXT, impact_type TEXT, impact_status TEXT, reason TEXT);
          CREATE TABLE IF NOT EXISTS plan (action_plan_id TEXT PRIMARY KEY, incident_id TEXT, status TEXT, rationale TEXT, expected_outcome TEXT, overall_risk TEXT, plan_hash TEXT, steps_json TEXT);
          CREATE TABLE IF NOT EXISTS event (event_id TEXT PRIMARY KEY, incident_id TEXT, created_at TEXT, actor_id TEXT, event_type TEXT, event_summary TEXT);
        """)


init_database()


def rows(query: str, params: tuple = ()) -> list[dict]:
    with db() as conn:
        return [dict(item) for item in conn.execute(query, params).fetchall()]


@app.get("/api/v2/status")
def status() -> dict:
    return {"environment": "local SQLite", "orchestrator": "ready", "policy_engine": "active", "database": "SQLite connected", "last_checked_at": datetime.now(timezone.utc).isoformat()}


@app.get("/api/v2/auth/mock-login")
def login(role: str = "commander") -> dict:
    return {"access_token": f"local-{role}-token", "token_type": "bearer"}


@app.get("/api/v2/incidents")
def incidents(state: str = "open") -> list[dict]:
    if state == "resolved":
        return rows("SELECT * FROM incident WHERE UPPER(status) = 'RESOLVED' ORDER BY detected_at DESC")
    if state == "all":
        return rows("SELECT * FROM incident ORDER BY detected_at DESC")
    return rows("SELECT * FROM incident WHERE UPPER(status) != 'RESOLVED' ORDER BY detected_at DESC")


@app.get("/api/v2/incidents/{incident_id}/hypotheses")
def hypotheses(incident_id: str) -> list[dict]: return rows("SELECT * FROM hypothesis WHERE incident_id = ?", (incident_id,))


@app.get("/api/v2/incidents/{incident_id}/evidence")
def evidence(incident_id: str) -> list[dict]: return rows("SELECT * FROM evidence WHERE incident_id = ?", (incident_id,))


@app.get("/api/v2/incidents/{incident_id}/impact")
def impact(incident_id: str) -> list[dict]: return rows("SELECT * FROM impact WHERE incident_id = ?", (incident_id,))


@app.get("/api/v2/incidents/{incident_id}/alerts")
def alerts(incident_id: str) -> list[dict]: return rows("SELECT * FROM alert WHERE incident_id = ?", (incident_id,))


@app.get("/api/v2/incidents/{incident_id}/plans")
def plans(incident_id: str) -> list[dict]:
    result = rows("SELECT * FROM plan WHERE incident_id = ?", (incident_id,))
    for item in result: item["steps"] = json.loads(item.pop("steps_json"))
    return result


@app.get("/api/v2/incidents/{incident_id}/events")
def events(incident_id: str) -> list[dict]: return rows("SELECT * FROM event WHERE incident_id = ? ORDER BY created_at", (incident_id,))


@app.get("/api/v2/incidents/{incident_id}/events/stream")
async def event_stream(incident_id: str) -> StreamingResponse:
    async def stream():
        for item in rows("SELECT event_id, created_at, actor_id, event_type, event_summary FROM event WHERE incident_id = ? ORDER BY created_at", (incident_id,)):
            yield f"data: {json.dumps({'id': item['event_id'], 'timestamp': item['created_at'], 'source': item['actor_id'], 'event_type': item['event_type'], 'message': item['event_summary']})}\n\n"
        yield ": connected\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream")


class Approval(BaseModel):
    decision: str
    plan_hash: str


@app.post("/api/v2/incidents/{incident_id}/plans/{plan_id}/approve")
def approve(incident_id: str, plan_id: str, approval: Approval) -> dict:
    with db() as conn:
        conn.execute("UPDATE plan SET status = 'APPROVED' WHERE action_plan_id = ?", (plan_id,))
        conn.execute("UPDATE incident SET status = 'EXECUTING' WHERE incident_id = ?", (incident_id,))
    return {"status": "approved", "decision": approval.decision}
