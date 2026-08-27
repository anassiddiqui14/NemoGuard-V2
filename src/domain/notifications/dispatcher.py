"""
NotificationPolicy + NotificationDispatcher (WP-ORG-002 §4.19-4.22).

    audit_event -> StatusProjector -> NotificationPolicy -> NotificationDispatcher -> Teams Adapter

Called from src/domain/orchestrator.py's _log_audit path (fire-and-forget,
best-effort) -- a Teams delivery failure must NEVER block alert ingestion,
investigation, approval, execution, or verification. Every public
dispatch() call in this module catches its own exceptions and only ever
records a FAILED delivery row; it never raises into the caller.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.store.postgres_database import PostgresDatabase
from src.domain.notifications.teams_adapter import build_card_for_update, post_to_webhook, resolve_webhook_url


def _generate_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


# Per spec §4.22: default allowlist of update_types that warrant an
# EXTERNAL (Teams) notification -- a strict subset of the full Commander
# Pulse allowlist in status_projector.py, since Pulse itself is meant to
# show more granular internal progress than Teams should ever see.
DEFAULT_EXTERNAL_NOTIFY_TYPES = {
    "PLAN_READY",
    "REINVESTIGATION_TRIGGERED",
    "PLAN_INVALIDATED",
    "EXECUTION_BLOCKED",
    "VERIFICATION_FAILED",
    "VERIFICATION_PASSED",
    "INCIDENT_RESOLVED",
    "INCIDENT_ESCALATED",
}


class NotificationDispatcher:
    def __init__(self, db: Optional[PostgresDatabase] = None):
        self.db = db or PostgresDatabase(
            os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db")
        )
        self.base_url = os.environ.get("NEMOGUARD_APP_BASE_URL", "http://localhost")

    def _matching_routes(self, incident_context: Dict[str, Any], update_type: str) -> list:
        """Loads enabled routes and filters by environment/service_pattern/
        severity_threshold/notify_on -- all evaluated here in Python
        (not SQL) since notify_on_json is a JSON array and severity
        ordering isn't naturally expressible as a simple SQL comparison."""
        severity_order = {"SEV_1": 1, "SEV_2": 2, "SEV_3": 3, "SEV_4": 4}
        incident_severity_rank = severity_order.get(incident_context.get("severity", "SEV_4"), 4)

        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT route_id, environment, service_pattern, severity_threshold, notify_on_json "
                "FROM teams_notification_route WHERE enabled = 1"
            )
            rows = cursor.fetchall()

        matched = []
        for route_id, environment, service_pattern, severity_threshold, notify_on_json in rows:
            try:
                notify_on = json.loads(notify_on_json or "[]")
            except Exception:
                notify_on = []
            # Empty notify_on list means "use the default allowlist" -- lets
            # a route be created with just routing info and inherit sane
            # defaults rather than requiring every event type spelled out.
            allowlist = set(notify_on) if notify_on else DEFAULT_EXTERNAL_NOTIFY_TYPES
            if update_type not in allowlist:
                continue
            if environment and environment != incident_context.get("environment"):
                continue
            if service_pattern and service_pattern not in (incident_context.get("service") or ""):
                continue
            if severity_threshold:
                threshold_rank = severity_order.get(severity_threshold, 4)
                if incident_severity_rank > threshold_rank:  # incident is LESS severe than threshold
                    continue
            matched.append(route_id)
        return matched

    def _load_incident_context(self, incident_id: str) -> Dict[str, Any]:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT status, severity, environment_id, primary_job_id, owner_team FROM incident WHERE incident_id = %s",
                (incident_id,),
            )
            row = cursor.fetchone()
        if not row:
            return {}
        return {
            "status": row[0], "severity": row[1], "environment": row[2],
            "service": row[3], "owner_team": row[4],
        }

    def _record_delivery(
        self, route_id: str, incident_id: str, source_update_id: Optional[str],
        update_type: str, status: str, error_message: Optional[str] = None,
    ) -> None:
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO teams_notification_delivery (
                        delivery_id, route_id, incident_id, source_update_id, update_type, status, error_message, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (route_id, source_update_id) DO NOTHING
                    """,
                    (
                        _generate_id("TMSG"), route_id, incident_id, source_update_id,
                        update_type, status, error_message, datetime.now(timezone.utc).isoformat(),
                    ),
                )
        except Exception as e:
            print(f"NotificationDispatcher: failed to record delivery log entry: {e}")

    def find_undispatched_updates(self, limit: int = 100) -> list:
        """
        Finds commander_status_update rows that don't yet have ANY
        teams_notification_delivery row recorded for them, regardless of
        which code path created the projection (the synchronous
        StatusProjector.get_pulse() used by the frontend's GET
        /commander/status polling, or this module's own background
        poller). Decoupling dispatch from projection this way avoids a
        race where whichever path happens to project a given audit_event
        first "wins" and the other silently never gets a chance to
        dispatch -- projection is idempotent per audit_event, but without
        this, only ONE of the two call sites would ever see it as
        "unprojected".
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT u.update_id, u.incident_id, u.update_type, u.headline, u.summary
                FROM commander_status_update u
                LEFT JOIN teams_notification_delivery d ON d.source_update_id = u.update_id
                WHERE d.delivery_id IS NULL
                ORDER BY u.created_at ASC
                LIMIT %s
                """,
                (limit,),
            )
            return cursor.fetchall()

    async def dispatch_all_pending(self) -> int:
        """Dispatches every commander_status_update that has no delivery
        row for ANY route yet. Marks it as considered (via a SKIPPED_NO_
        MATCHING_ROUTE delivery row against a sentinel route) even when no
        route matches, so it is never re-scanned on every tick forever."""
        rows = self.find_undispatched_updates()
        count = 0
        for update_id, incident_id, update_type, headline, summary in rows:
            try:
                await self.dispatch(incident_id, update_id, update_type, headline, summary)
                count += 1
            except Exception as e:
                print(f"NotificationDispatcher: dispatch_all_pending failed for {update_id}: {e}")
            # Always record a sentinel row so this update_id is never
            # rescanned even if zero routes matched (dispatch() only
            # records delivery rows for MATCHING routes).
            self._record_delivery("__NO_ROUTE__", incident_id, update_id, update_type, "CONSIDERED")
        return count

    async def dispatch(
        self, incident_id: str, update_id: Optional[str], update_type: str, headline: str, summary: Optional[str],
    ) -> None:
        """Best-effort dispatch to every matching route. Never raises --
        any failure (missing webhook config, network error, bad response)
        is caught, logged, and recorded as a FAILED/SKIPPED delivery row
        rather than propagating."""
        try:
            incident_context = self._load_incident_context(incident_id)
            route_ids = self._matching_routes(incident_context, update_type)
        except Exception as e:
            print(f"NotificationDispatcher: failed to resolve routes for {incident_id}/{update_type}: {e}")
            return

        for route_id in route_ids:
            try:
                webhook_url = resolve_webhook_url(route_id)
                if not webhook_url:
                    self._record_delivery(route_id, incident_id, update_id, update_type, "SKIPPED_NO_WEBHOOK_CONFIGURED")
                    continue
                card = build_card_for_update(incident_id, update_type, headline, summary, incident_context, self.base_url)
                await post_to_webhook(webhook_url, card)
                self._record_delivery(route_id, incident_id, update_id, update_type, "SENT")
            except Exception as e:
                print(f"NotificationDispatcher: delivery to route {route_id} failed: {e}")
                self._record_delivery(route_id, incident_id, update_id, update_type, "FAILED", error_message=str(e))
