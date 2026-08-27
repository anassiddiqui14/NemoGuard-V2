"""
Commander Pulse status projector (WP-ORG-002 §4.4/4.5).

Converts raw audit_event rows into meaningful, operator-facing
commander_status_update rows using deterministic templates -- never
exposes chain-of-thought/reasoning tokens, only structured facts already
present on the audit event.

Idempotent: commander_status_update.source_audit_event_id has a UNIQUE
index (see migrations/012_commander_live.sql), so re-projecting the same
audit event twice is a safe no-op via ON CONFLICT DO NOTHING.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.store.postgres_database import PostgresDatabase


def _generate_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


# Allowlisted event types this projector will turn into a Commander Pulse
# update, with a deterministic (headline, summary) template. `event_type`
# values are exactly what _log_audit already writes across
# src/domain/orchestrator.py -- no new event types are introduced here,
# this only adds a presentation layer on top of what already exists.
#
# Each template receives the audit row (event_summary, actor_id) and
# returns (update_type, headline, summary, severity, notify_external).
def _template(event_type: str, summary: str, actor: str) -> Optional[Dict[str, Any]]:
    mapping = {
        "ALERT_CORRELATED": (
            "CORRELATION_DECIDED", "Alert correlated to this incident", summary, None, False,
        ),
        "HYPOTHESIS_CREATED": (
            "HYPOTHESIS_CHANGED", "Root-cause hypothesis updated", summary, None, False,
        ),
        "IMPACT_CALCULATED": (
            "IMPACT_UPDATED", "Business impact assessed", summary, None, False,
        ),
        "RUNBOOK_RETRIEVED": (
            "RUNBOOK_SELECTED", "Recovery runbook matched", summary, None, False,
        ),
        "SAFETY_VALIDATION_PASSED": (
            "CRITIC_REVIEW_COMPLETED", "Safety review passed", summary, None, False,
        ),
        "SAFETY_VALIDATION_FAILED": (
            "CRITIC_REVIEW_COMPLETED", "Safety review flagged a concern", summary, "warning", False,
        ),
        "PLAN_CREATED": (
            "PLAN_READY", "Recovery plan is ready for review", summary, None, True,
        ),
        "PLAN_REVISED": (
            "PLAN_INVALIDATED", "Recovery plan was revised", summary, None, True,
        ),
        "REINVESTIGATION_TRIGGERED": (
            "REINVESTIGATION_TRIGGERED", "Re-investigation triggered by new evidence", summary, None, True,
        ),
        "APPROVAL_RECORDED": (
            "APPROVAL_RECEIVED", "Recovery plan approved", summary, None, True,
        ),
        "ACTION_EXECUTED": (
            "EXECUTION_STEP_COMPLETED", "Recovery action executed", summary, None, False,
        ),
        "MANUAL_ACTION_REQUIRED": (
            "EXECUTION_BLOCKED", "Execution blocked -- manual action required", summary, "warning", True,
        ),
        "VERIFICATION_PASSED": (
            "VERIFICATION_PASSED", "Independent verification passed", summary, None, True,
        ),
        "VERIFICATION_FAILED": (
            "VERIFICATION_FAILED", "Independent verification failed", summary, "critical", True,
        ),
        "INCIDENT_RESOLVED": (
            "INCIDENT_RESOLVED", "Incident resolved", summary, None, True,
        ),
        "INCIDENT_ESCALATED": (
            "INCIDENT_ESCALATED", "Incident escalated for human attention", summary, "critical", True,
        ),
        "INCIDENT_AUTO_RESOLVED_EXTERNALLY": (
            "INCIDENT_RESOLVED", "Incident auto-resolved from an external recovery signal", summary, None, True,
        ),
        "INCIDENT_STATE_CHANGED": (
            "LIFECYCLE_STATE_CHANGED", "Incident status updated", summary, None, False,
        ),
        "PLAN_REJECTED": (
            "PLAN_INVALIDATED", "Recovery plan rejected by operator", summary, None, False,
        ),
        "HUMAN_GUIDANCE_RECEIVED": (
            "HUMAN_GUIDANCE_RECEIVED", "Operator provided guidance", summary, None, False,
        ),
        "CONFIRMED_FACT_ADDED": (
            "CONFIRMED_FACT_ADDED", "Operator added a confirmed fact", summary, None, False,
        ),
    }
    entry = mapping.get(event_type)
    if not entry:
        return None
    update_type, headline, body, severity, notify = entry
    return {
        "update_type": update_type,
        "headline": headline,
        "summary": body,
        "severity": severity,
        "notify_external": notify,
    }


class StatusProjector:
    def __init__(self, db: Optional[PostgresDatabase] = None):
        import os
        self.db = db or PostgresDatabase(
            os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db")
        )

    def project_audit_event(
        self, audit_event_id: str, incident_id: str, event_type: str, event_summary: str, actor_id: str,
    ) -> Optional[str]:
        """Projects a single audit_event row into commander_status_update,
        if its event_type is in the allowlist. Returns the new update_id,
        or None if this event_type is not projected (e.g. low-level
        FALLBACK_*_STARTED diagnostic events) or the event was already
        projected (idempotent no-op)."""
        template = _template(event_type, event_summary, actor_id)
        if not template:
            return None

        update_id = _generate_id("CUPD")
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO commander_status_update (
                    update_id, incident_id, source_audit_event_id, update_type,
                    created_at, headline, summary, severity, notify_external
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_audit_event_id) DO NOTHING
                RETURNING update_id
                """,
                (
                    update_id, incident_id, audit_event_id, template["update_type"],
                    now, template["headline"], template["summary"], template["severity"],
                    int(template["notify_external"]),
                ),
            )
            row = cursor.fetchone()
        return row[0] if row else None

    def project_unprojected_events(self, incident_id: str) -> int:
        """Catches up any audit_event rows for this incident that don't yet
        have a corresponding commander_status_update -- used both for
        backfilling incidents created before this feature existed, and as
        a cheap way to keep Commander Pulse in sync without needing a
        real-time trigger/listener."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT a.audit_event_id, a.event_type, a.event_summary, a.actor_id
                FROM audit_event a
                LEFT JOIN commander_status_update c ON c.source_audit_event_id = a.audit_event_id
                WHERE a.incident_id = %s AND c.update_id IS NULL
                ORDER BY a.created_at ASC
                """,
                (incident_id,),
            )
            rows = cursor.fetchall()
        count = 0
        for audit_event_id, event_type, event_summary, actor_id in rows:
            if self.project_audit_event(audit_event_id, incident_id, event_type, event_summary, actor_id):
                count += 1
        return count

    def get_pulse(self, incident_id: str, limit: int = 50) -> list:
        self.project_unprojected_events(incident_id)
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT update_id, update_type, created_at, headline, summary, severity, notify_external
                FROM commander_status_update
                WHERE incident_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (incident_id, limit),
            )
            cols = [c[0] for c in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]
