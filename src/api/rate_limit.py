"""
Lightweight in-process rate limiting.

Per docs/NemoGuard_Enterprise_Hardening_and_Productization_Build_Plan.md
Priority 9 (13.4) / WP-002: both `/api/v2/ingest/webhook` and the
simulator's `/trigger/ai` accept unlimited unauthenticated (webhook) or
authenticated (trigger/ai) requests and can each trigger expensive LLM
calls -- a real cost/DoS risk with zero current protection.

This is intentionally a simple in-memory sliding-window limiter, not a
distributed one (Redis-backed) -- appropriate for the current single-process
deployment. It should be swapped for a shared-state limiter (e.g. Redis)
before running multiple API replicas behind a load balancer, since each
process would otherwise track its own independent window.
"""

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict

from fastapi import HTTPException, Request


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> bool:
        """Returns True if the request identified by `key` is allowed, False if it should be rejected."""
        now = time.monotonic()
        with self._lock:
            window = self._hits[key]
            cutoff = now - self.window_seconds
            while window and window[0] < cutoff:
                window.popleft()
            if len(window) >= self.max_requests:
                return False
            window.append(now)
            return True

    def reset(self):
        """Test helper: clear all tracked state."""
        with self._lock:
            self._hits.clear()


def _client_ip(request: Request) -> str:
    # Respect X-Forwarded-For if present (behind a reverse proxy), else the
    # direct peer address.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


# Webhook ingestion: generous enough for real monitoring bursts, tight
# enough to bound worst-case LLM spend from a single abusive source.
webhook_limiter = SlidingWindowRateLimiter(max_requests=60, window_seconds=60)


def enforce_webhook_rate_limit(request: Request) -> None:
    key = _client_ip(request)
    if not webhook_limiter.check(key):
        raise HTTPException(
            status_code=429,
            detail="Too many webhook requests from this source. Please slow down.",
        )
