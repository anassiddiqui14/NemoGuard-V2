"""
Unit tests for src/api/webhook_security.py.

Per docs/NemoGuard_Enterprise_Hardening_and_Productization_Build_Plan.md
Priority 9 sections 13.3 (Authentication) and 13.5 (Replay protection).
"""

import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from src.api.webhook_security import (
    verify_webhook_signature,
    enforce_timestamp_bounds,
    enforce_replay_protection,
    EventIdDedupCache,
    _get_configured_secret,
)


class TestGetConfiguredSecret:
    def test_returns_none_when_no_secret_configured(self, monkeypatch):
        monkeypatch.delenv("WEBHOOK_SECRET_DATADOG", raising=False)
        assert _get_configured_secret("datadog") is None

    def test_returns_secret_when_configured_uppercase_normalized(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_SECRET_DATADOG", "my-secret-123")
        assert _get_configured_secret("datadog") == "my-secret-123"

    def test_normalizes_non_alphanumeric_characters_in_source_name(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_SECRET_PAGER_DUTY", "pd-secret")
        assert _get_configured_secret("pager-duty") == "pd-secret"

    def test_empty_source_returns_none(self):
        assert _get_configured_secret("") is None


class TestVerifyWebhookSignature:
    def test_source_with_no_configured_secret_is_allowed_without_a_signature(self, monkeypatch):
        monkeypatch.delenv("WEBHOOK_SECRET_UNCONFIGURED_SOURCE", raising=False)
        # Should not raise, even with no signature header at all.
        verify_webhook_signature(b'{"a": 1}', "unconfigured_source", None)

    def test_configured_source_with_missing_signature_header_is_rejected(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_SECRET_DATADOG", "shh")
        with pytest.raises(HTTPException) as exc_info:
            verify_webhook_signature(b'{"a": 1}', "datadog", None)
        assert exc_info.value.status_code == 401

    def test_configured_source_with_malformed_signature_header_is_rejected(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_SECRET_DATADOG", "shh")
        with pytest.raises(HTTPException) as exc_info:
            verify_webhook_signature(b'{"a": 1}', "datadog", "not-the-right-format")
        assert exc_info.value.status_code == 401

    def test_configured_source_with_valid_signature_is_accepted(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_SECRET_DATADOG", "shh")
        body = b'{"a": 1}'
        expected = hmac.new(b"shh", body, hashlib.sha256).hexdigest()
        # Should not raise.
        verify_webhook_signature(body, "datadog", f"sha256={expected}")

    def test_configured_source_with_wrong_signature_is_rejected(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_SECRET_DATADOG", "shh")
        body = b'{"a": 1}'
        wrong_sig = hmac.new(b"different-secret", body, hashlib.sha256).hexdigest()
        with pytest.raises(HTTPException) as exc_info:
            verify_webhook_signature(body, "datadog", f"sha256={wrong_sig}")
        assert exc_info.value.status_code == 401

    def test_signature_computed_over_a_different_body_is_rejected(self, monkeypatch):
        """
        Confirms the signature is checked against the ACTUAL raw body passed
        in, not just any well-formed signature -- tampering with the body
        after signing must invalidate the signature.
        """
        monkeypatch.setenv("WEBHOOK_SECRET_DATADOG", "shh")
        original_body = b'{"a": 1}'
        tampered_body = b'{"a": 2}'
        sig_for_original = hmac.new(b"shh", original_body, hashlib.sha256).hexdigest()
        with pytest.raises(HTTPException) as exc_info:
            verify_webhook_signature(tampered_body, "datadog", f"sha256={sig_for_original}")
        assert exc_info.value.status_code == 401


class TestEnforceTimestampBounds:
    def test_payload_with_no_timestamp_field_is_allowed(self):
        # Should not raise -- most webhook shapes don't carry a recognizable timestamp.
        enforce_timestamp_bounds({"message": "no timestamp here"})

    def test_recent_timestamp_is_allowed(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        enforce_timestamp_bounds({"occurred_at": now_iso})

    def test_timestamp_too_far_in_the_future_is_rejected(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        with pytest.raises(HTTPException) as exc_info:
            enforce_timestamp_bounds({"occurred_at": future})
        assert exc_info.value.status_code == 422

    def test_timestamp_too_far_in_the_past_is_rejected(self):
        stale = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        with pytest.raises(HTTPException) as exc_info:
            enforce_timestamp_bounds({"timestamp": stale})
        assert exc_info.value.status_code == 422

    def test_unparseable_timestamp_field_is_ignored_rather_than_erroring(self):
        # If the field is present but not a valid timestamp, this should not
        # itself become a hard failure -- it just means we can't apply the
        # bounds check for this payload.
        enforce_timestamp_bounds({"occurred_at": "not-a-real-timestamp"})

    def test_checks_multiple_recognized_timestamp_field_names(self):
        stale = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        for field in ("occurred_at", "timestamp", "opened_at", "event_time", "created_at"):
            with pytest.raises(HTTPException):
                enforce_timestamp_bounds({field: stale})


class TestEventIdDedupCache:
    def test_first_occurrence_of_an_event_id_is_allowed(self):
        cache = EventIdDedupCache()
        assert cache.check_and_record("evt-1") is True

    def test_duplicate_event_id_within_ttl_is_rejected(self):
        cache = EventIdDedupCache()
        assert cache.check_and_record("evt-1") is True
        assert cache.check_and_record("evt-1") is False

    def test_different_event_ids_are_independently_tracked(self):
        cache = EventIdDedupCache()
        assert cache.check_and_record("evt-1") is True
        assert cache.check_and_record("evt-2") is True
        assert cache.check_and_record("evt-1") is False
        assert cache.check_and_record("evt-2") is False

    def test_expired_entries_are_evicted_and_event_id_becomes_reusable(self):
        cache = EventIdDedupCache(ttl_seconds=0.05)
        assert cache.check_and_record("evt-1") is True
        time.sleep(0.1)
        assert cache.check_and_record("evt-1") is True

    def test_size_cap_evicts_oldest_entry_rather_than_growing_unbounded(self):
        cache = EventIdDedupCache(ttl_seconds=3600, max_size=2)
        assert cache.check_and_record("evt-1") is True
        assert cache.check_and_record("evt-2") is True
        # Cache is now at max_size=2; a third distinct event_id should evict
        # the oldest ("evt-1") rather than being rejected or growing past the cap.
        assert cache.check_and_record("evt-3") is True
        # evt-1 was evicted, so it's treated as new again.
        assert cache.check_and_record("evt-1") is True

    def test_reset_clears_all_tracked_state(self):
        cache = EventIdDedupCache()
        cache.check_and_record("evt-1")
        cache.reset()
        assert cache.check_and_record("evt-1") is True


class TestEnforceReplayProtection:
    def test_payload_without_event_id_only_checks_timestamp_bounds(self):
        # No event_id -- should not raise on first OR second call, since
        # there's nothing to dedup against.
        enforce_replay_protection({"message": "no event id"})
        enforce_replay_protection({"message": "no event id"})

    def test_payload_with_event_id_is_rejected_on_second_occurrence(self):
        from src.api.webhook_security import _dedup_cache

        _dedup_cache.reset()
        payload = {"event_id": "unique-evt-abc123", "message": "hello"}
        enforce_replay_protection(payload)  # first time: allowed
        with pytest.raises(HTTPException) as exc_info:
            enforce_replay_protection(payload)  # second time: rejected
        assert exc_info.value.status_code == 409

    def test_stale_timestamp_is_rejected_even_before_the_dedup_check(self):
        stale = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        with pytest.raises(HTTPException) as exc_info:
            enforce_replay_protection({"event_id": "some-evt", "occurred_at": stale})
        assert exc_info.value.status_code == 422
