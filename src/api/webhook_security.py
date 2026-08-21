"""
Webhook signature authentication and replay protection.

Per docs/NemoGuard_Enterprise_Hardening_and_Productization_Build_Plan.md
Priority 9 sections 13.3 (Authentication) and 13.5 (Replay protection).
WP-002 already covered section 13.2 (payload size/depth/string-length
validation, see webhook_validation.py) and section 13.4 (per-IP rate
limiting, see rate_limit.py). This module fills the remaining two gaps:

1. HMAC signature verification (13.3) -- `/api/v2/ingest/webhook` is
   intentionally left reachable by unauthenticated callers (real
   monitoring systems like Datadog/PagerDuty/CloudWatch can't easily be
   issued a NemoGuard JWT), but that meant ANY caller who could reach the
   endpoint could inject arbitrary alerts/incidents with zero proof of
   origin. This adds OPT-IN, per-source HMAC-SHA256 signature verification:
   once an operator configures a secret for a given `source` value (via
   `WEBHOOK_SECRET_<SOURCE>` env vars), any request claiming that source
   MUST present a valid `X-NemoGuard-Signature: sha256=<hex>` header
   computed over the raw request body, or it is rejected with 401. Sources
   with no configured secret remain open (preserving the existing
   simulator/demo flow and any as-yet-unconfigured real integration) --
   this is a deliberate, documented trust model: "authenticate what you
   can, don't break what you haven't configured yet."

2. Replay protection (13.5) -- a captured/replayed webhook payload
   (accidentally re-sent by a flaky monitoring system, or maliciously
   replayed by an attacker who sniffed a valid signed request) could
   previously re-trigger the same alert/incident processing indefinitely.
   If the payload includes an `event_id` (per the build plan's canonical
   envelope section 13.1) or a recognizable timestamp field, this enforces:
     - a bounded acceptance window (reject events too far in the future,
       which would indicate clock skew or spoofing, or too old, which
       indicates a stale replay)
     - a TTL-bound in-memory dedup cache keyed on event_id, rejecting any
       exact repeat within the window
   Like rate_limit.py, this is an in-process cache appropriate for the
   current single-process deployment; it should move to a shared store
   (e.g. Redis) before running multiple API replicas.
"""

import hashlib
import hmac
import os
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Optional

from fastapi import HTTPException

# How far into the future/past an event's timestamp may be and still be
# accepted. Generous enough to tolerate real clock skew between a
# third-party monitoring system and NemoGuard, tight enough to reject a
# stale replayed payload or an obviously spoofed future timestamp.
MAX_FUTURE_SKEW = timedelta(minutes=5)
MAX_PAST_AGE = timedelta(days=7)

# How long a given event_id is remembered for replay-dedup purposes, and
# the hard cap on cache size (to bound memory even under sustained load).
_EVENT_ID_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days, matching MAX_PAST_AGE
_MAX_TRACKED_EVENT_IDS = 50_000

_TIMESTAMP_FIELDS = ("occurred_at", "timestamp", "opened_at", "event_time", "created_at")


def _get_configured_secret(source: str) -> Optional[str]:
    """
    Looks up an HMAC secret for `source` via the `WEBHOOK_SECRET_<SOURCE>`
    environment variable (source uppercased, non-alphanumeric characters
    replaced with underscores -- e.g. source="pager-duty" resolves to
    WEBHOOK_SECRET_PAGER_DUTY). Returns None if unconfigured -- callers
    treat that as "this source is not yet authenticated" rather than an
    error, per the opt-in trust model described in the module docstring.
    """
    if not source:
        return None
    normalized = "".join(c if c.isalnum() else "_" for c in source.upper())
    return os.environ.get(f"WEBHOOK_SECRET_{normalized}")


def verify_webhook_signature(raw_body: bytes, source: str, signature_header: Optional[str]) -> None:
    """
    Raises HTTPException(401) if `source` has a configured secret but the
    provided signature is missing or doesn't match. No-ops (silently
    allows) if `source` has no configured secret at all.

    Expected header format: "sha256=<hex-encoded HMAC-SHA256 digest>",
    computed as HMAC-SHA256(secret, raw_body).
    """
    secret = _get_configured_secret(source)
    if secret is None:
        # No secret configured for this source -- authentication is not
        # enforced for it (see module docstring for the trust model).
        return

    if not signature_header:
        raise HTTPException(
            status_code=401,
            detail=f"Missing X-NemoGuard-Signature header; a secret is configured for source '{source}'.",
        )

    prefix = "sha256="
    if not signature_header.startswith(prefix):
        raise HTTPException(status_code=401, detail="Malformed signature header; expected 'sha256=<hex digest>'.")

    provided_hex = signature_header[len(prefix):].strip()
    expected_hex = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(provided_hex, expected_hex):
        raise HTTPException(status_code=401, detail="Webhook signature verification failed.")


def _extract_event_timestamp(payload: dict) -> Optional[datetime]:
    for field in _TIMESTAMP_FIELDS:
        raw = payload.get(field)
        if not raw:
            continue
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except (ValueError, TypeError):
            continue
    return None


def enforce_timestamp_bounds(payload: dict) -> None:
    """
    Raises HTTPException(422) if the payload carries a recognizable
    timestamp field that is too far in the future (likely clock skew or
    spoofing) or too far in the past (likely a stale replayed payload).
    No-ops if no recognizable timestamp field is present -- most webhook
    payload shapes are not required to carry one, and this is a defense
    -in-depth measure, not a schema requirement.
    """
    event_time = _extract_event_timestamp(payload)
    if event_time is None:
        return

    now = datetime.now(timezone.utc)
    if event_time > now + MAX_FUTURE_SKEW:
        raise HTTPException(
            status_code=422,
            detail=f"Event timestamp {event_time.isoformat()} is too far in the future (max skew {MAX_FUTURE_SKEW}).",
        )
    if event_time < now - MAX_PAST_AGE:
        raise HTTPException(
            status_code=422,
            detail=f"Event timestamp {event_time.isoformat()} is older than the maximum accepted age ({MAX_PAST_AGE}).",
        )


class EventIdDedupCache:
    """
    TTL-bound, size-bounded in-memory cache of recently-seen event_ids, used
    to reject exact-duplicate webhook deliveries (accidental re-sends or
    malicious replays of a captured request).
    """

    def __init__(self, ttl_seconds: float = _EVENT_ID_TTL_SECONDS, max_size: int = _MAX_TRACKED_EVENT_IDS):
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._seen: "OrderedDict[str, float]" = OrderedDict()
        self._lock = Lock()

    def _evict_expired(self, now: float) -> None:
        cutoff = now - self.ttl_seconds
        while self._seen:
            oldest_id, oldest_ts = next(iter(self._seen.items()))
            if oldest_ts < cutoff:
                self._seen.popitem(last=False)
            else:
                break

    def check_and_record(self, event_id: str) -> bool:
        """
        Returns True if `event_id` has NOT been seen within the TTL window
        (and records it as seen now, allowing the caller to proceed).
        Returns False if it WAS already seen within the window (the caller
        should reject this request as a replay/duplicate).
        """
        now = time.monotonic()
        with self._lock:
            self._evict_expired(now)

            if event_id in self._seen:
                return False

            if len(self._seen) >= self.max_size:
                # Hard size cap reached even after TTL eviction (e.g. under
                # sustained abusive load) -- evict the single oldest entry
                # to make room rather than growing unbounded.
                self._seen.popitem(last=False)

            self._seen[event_id] = now
            return True

    def reset(self):
        """Test helper: clear all tracked state."""
        with self._lock:
            self._seen.clear()


_dedup_cache = EventIdDedupCache()


def enforce_replay_protection(payload: dict) -> None:
    """
    Full replay-protection check for a webhook payload (section 13.5):
    validates the timestamp bounds (if a recognizable timestamp field is
    present), then -- if the payload carries an `event_id` field (per the
    build plan's canonical envelope, section 13.1) -- rejects it with
    HTTPException(409) if that exact event_id has already been processed
    within the dedup window.

    No-ops the event_id check entirely if the payload has no `event_id`
    field -- most real-world webhook shapes (Datadog, PagerDuty, ad-hoc
    Airflow callbacks, etc.) do not carry one today, and this is
    defense-in-depth for sources that DO provide one, not a schema
    requirement placed on every integration.
    """
    enforce_timestamp_bounds(payload)

    event_id = payload.get("event_id")
    if not event_id:
        return

    if not _dedup_cache.check_and_record(str(event_id)):
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate event_id '{event_id}' -- this webhook payload has already been processed.",
        )
