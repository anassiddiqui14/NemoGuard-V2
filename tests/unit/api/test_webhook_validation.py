"""
Unit tests for src/api/webhook_validation.py -- bounding untrusted webhook
payloads (size, nesting depth, item counts, string length) before they are
ever handed to an LLM.
"""

import pytest
from fastapi import HTTPException

from src.api.webhook_validation import (
    MAX_ITEMS_PER_LEVEL,
    MAX_JSON_DEPTH,
    MAX_PAYLOAD_BYTES,
    MAX_STRING_LENGTH,
    validate_webhook_payload,
)


class TestValidateWebhookPayload:
    def test_normal_payload_passes(self):
        payload = {
            "severity": "critical",
            "message": "Job failed",
            "tags": ["service:foo", "env:prod"],
        }
        # Should not raise.
        validate_webhook_payload(payload)

    def test_non_dict_payload_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_webhook_payload(["not", "a", "dict"])  # type: ignore[arg-type]
        assert exc_info.value.status_code == 422

    def test_oversized_payload_rejected(self):
        # Build a payload whose serialized form exceeds MAX_PAYLOAD_BYTES.
        huge_string = "x" * (MAX_PAYLOAD_BYTES + 1000)
        payload = {"message": huge_string}
        with pytest.raises(HTTPException) as exc_info:
            validate_webhook_payload(payload)
        assert exc_info.value.status_code == 413

    def test_excessive_nesting_depth_rejected(self):
        # Build a dict nested deeper than MAX_JSON_DEPTH.
        payload = {}
        current = payload
        for _ in range(MAX_JSON_DEPTH + 5):
            current["nested"] = {}
            current = current["nested"]
        with pytest.raises(HTTPException) as exc_info:
            validate_webhook_payload(payload)
        assert exc_info.value.status_code == 422

    def test_excessive_items_at_one_level_rejected(self):
        payload = {f"key_{i}": i for i in range(MAX_ITEMS_PER_LEVEL + 10)}
        with pytest.raises(HTTPException) as exc_info:
            validate_webhook_payload(payload)
        assert exc_info.value.status_code == 422

    def test_excessive_array_length_rejected(self):
        payload = {"items": list(range(MAX_ITEMS_PER_LEVEL + 10))}
        with pytest.raises(HTTPException) as exc_info:
            validate_webhook_payload(payload)
        assert exc_info.value.status_code == 422

    def test_excessively_long_string_value_rejected(self):
        payload = {"message": "y" * (MAX_STRING_LENGTH + 10)}
        with pytest.raises(HTTPException) as exc_info:
            validate_webhook_payload(payload)
        assert exc_info.value.status_code == 422

    def test_reasonable_nested_structure_passes(self):
        payload = {
            "alert": {
                "id": "abc123",
                "attributes": {
                    "tags": ["a", "b", "c"],
                    "metadata": {"region": "us-east-1"},
                },
            }
        }
        validate_webhook_payload(payload)

    def test_non_serializable_payload_rejected(self):
        class NotSerializable:
            pass

        with pytest.raises(HTTPException) as exc_info:
            validate_webhook_payload({"bad": NotSerializable()})
        assert exc_info.value.status_code == 422
