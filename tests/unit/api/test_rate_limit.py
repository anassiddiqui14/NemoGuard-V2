"""
Unit tests for src/api/rate_limit.py -- the in-process sliding-window
rate limiter protecting /api/v2/ingest/webhook.
"""

import time

import pytest
from fastapi import HTTPException, Request

from src.api.rate_limit import (
    SlidingWindowRateLimiter,
    _client_ip,
    enforce_webhook_rate_limit,
    webhook_limiter,
)


class TestSlidingWindowRateLimiter:
    def test_allows_requests_under_the_limit(self):
        limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60)
        assert limiter.check("client-a") is True
        assert limiter.check("client-a") is True
        assert limiter.check("client-a") is True

    def test_rejects_requests_over_the_limit(self):
        limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60)
        assert limiter.check("client-a") is True
        assert limiter.check("client-a") is True
        assert limiter.check("client-a") is False

    def test_different_keys_are_tracked_independently(self):
        limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)
        assert limiter.check("client-a") is True
        # client-b has its own independent budget.
        assert limiter.check("client-b") is True
        # client-a is now over budget.
        assert limiter.check("client-a") is False

    def test_old_hits_expire_out_of_the_window(self):
        limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=0.05)
        assert limiter.check("client-a") is True
        assert limiter.check("client-a") is False
        time.sleep(0.1)
        # The window has now elapsed, so the old hit should no longer count.
        assert limiter.check("client-a") is True

    def test_reset_clears_all_state(self):
        limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)
        limiter.check("client-a")
        assert limiter.check("client-a") is False
        limiter.reset()
        assert limiter.check("client-a") is True


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    """Minimal stand-in for fastapi.Request, avoiding a full ASGI scope."""

    def __init__(self, headers=None, client_host="1.2.3.4"):
        self.headers = headers or {}
        self.client = _FakeClient(client_host) if client_host else None


class TestClientIp:
    def test_uses_direct_peer_address_by_default(self):
        req = _FakeRequest(client_host="10.0.0.5")
        assert _client_ip(req) == "10.0.0.5"

    def test_prefers_x_forwarded_for_when_present(self):
        req = _FakeRequest(headers={"x-forwarded-for": "203.0.113.9, 10.0.0.1"}, client_host="10.0.0.1")
        assert _client_ip(req) == "203.0.113.9"

    def test_falls_back_to_unknown_when_no_client_info(self):
        req = _FakeRequest(client_host=None)
        assert _client_ip(req) == "unknown"


class TestEnforceWebhookRateLimit:
    def setup_method(self):
        webhook_limiter.reset()

    def teardown_method(self):
        webhook_limiter.reset()

    def test_allows_requests_within_budget(self):
        req = _FakeRequest(client_host="9.9.9.9")
        # Should not raise for the first several requests (well under the 60/min default).
        for _ in range(5):
            enforce_webhook_rate_limit(req)

    def test_raises_429_once_budget_exhausted(self):
        req = _FakeRequest(client_host="8.8.8.8")
        # Exhaust the default budget (60 requests/minute).
        for _ in range(60):
            enforce_webhook_rate_limit(req)
        with pytest.raises(HTTPException) as exc_info:
            enforce_webhook_rate_limit(req)
        assert exc_info.value.status_code == 429
