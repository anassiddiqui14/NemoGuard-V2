"""
Teams adapter (WP-ORG-002 §4.20 Phase A, §4.23-4.27).

Posts an Adaptive Card to a Teams Workflows webhook. The webhook URL is
NEVER read from the database (see migrations/013_teams_notifications.sql
comment) -- it is resolved from the environment variable
TEAMS_WEBHOOK_URL_<ROUTE_ID> at dispatch time, matching how NVIDIA_API_KEY
and every other credential in this codebase is sourced from the
environment rather than a config table.
"""
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx


def _card(title: str, facts: list, body_text: str, deep_link: Optional[str] = None) -> Dict[str, Any]:
    """Builds a minimal Adaptive Card payload compatible with a Teams
    Workflows "Post a card in a channel" trigger. Kept intentionally
    simple (title + fact list + body + optional deep-link button) to
    match every card example in spec §4.23-4.27 without over-engineering
    a richer template system this deployment doesn't need yet."""
    body = [
        {"type": "TextBlock", "text": title, "weight": "Bolder", "size": "Medium", "wrap": True},
        {"type": "FactSet", "facts": [{"title": k, "value": str(v)} for k, v in facts]},
        {"type": "TextBlock", "text": body_text, "wrap": True, "spacing": "Medium"},
    ]
    actions = []
    if deep_link:
        actions.append({"type": "Action.OpenUrl", "title": "Open in NemoGuard", "url": deep_link})
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": body,
        "actions": actions,
    }
    # Teams Workflows webhooks expect an attachments envelope, not a bare card.
    return {
        "type": "message",
        "attachments": [
            {"contentType": "application/vnd.microsoft.card.adaptive", "content": card}
        ],
    }


def build_card_for_update(
    incident_id: str, update_type: str, headline: str, summary: Optional[str],
    incident_context: Dict[str, Any], base_url: str,
) -> Dict[str, Any]:
    """Builds the appropriate card shape for a given commander_status_update
    update_type, following the exact card examples in spec §4.23-4.27."""
    deep_link = f"{base_url.rstrip('/')}/incidents/{incident_id}"
    severity = incident_context.get("severity", "UNKNOWN")
    status = incident_context.get("status", "UNKNOWN")
    service = incident_context.get("service") or incident_context.get("owner_team") or "N/A"

    if update_type in ("PLAN_READY",):
        title = "NemoGuard Recovery Plan Ready"
        facts = [("Incident", incident_id), ("Approval", "REQUIRED"), ("Status", status)]
    elif update_type in ("VERIFICATION_FAILED",):
        title = "NemoGuard Verification Failed"
        facts = [("Incident", incident_id), ("Severity", severity), ("Status", "OPEN")]
    elif update_type in ("INCIDENT_RESOLVED",):
        title = "NemoGuard Incident Resolved"
        facts = [("Incident", incident_id), ("Service", service)]
    elif update_type in ("INCIDENT_ESCALATED",):
        title = "NemoGuard Incident Escalated"
        facts = [("Incident", incident_id), ("Severity", severity), ("Status", status)]
    elif update_type in ("HYPOTHESIS_CHANGED", "IMPACT_UPDATED"):
        title = "NemoGuard Investigation Update"
        facts = [("Incident", incident_id), ("Service", service), ("Status", status)]
    else:
        title = "NemoGuard Incident Update"
        facts = [("Incident", incident_id), ("Severity", severity), ("Status", status)]

    return _card(title, facts, summary or headline, deep_link)


async def post_to_webhook(webhook_url: str, card_payload: Dict[str, Any], timeout_seconds: float = 10.0) -> None:
    """Posts the card payload to a Teams Workflows webhook URL. Raises on
    any failure -- callers (NotificationDispatcher) are responsible for
    catching this and recording it as a FAILED delivery rather than
    letting it propagate into incident/investigation logic."""
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        resp = await client.post(webhook_url, json=card_payload)
        resp.raise_for_status()


def resolve_webhook_url(route_id: str) -> Optional[str]:
    """Resolves TEAMS_WEBHOOK_URL_<ROUTE_ID> (uppercased, non-alnum
    replaced with underscore) from the environment. Returns None if not
    configured for this route -- callers should record this as
    SKIPPED_NO_WEBHOOK_CONFIGURED rather than treating it as an error,
    since most deployments will only configure a subset of routes."""
    env_key = "TEAMS_WEBHOOK_URL_" + "".join(c if c.isalnum() else "_" for c in route_id.upper())
    return os.environ.get(env_key)
