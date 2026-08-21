"""
Webhook payload validation.

Per docs/NemoGuard_Enterprise_Hardening_and_Productization_Build_Plan.md
Priority 9 (13.2) / WP-002: `ingest_webhook(payload: dict)` previously
accepted arbitrary JSON with no size limit or schema validation before
handing it directly to the WatcherAgent LLM call -- an unauthenticated
endpoint that could be used to smuggle oversized or maliciously-deep
payloads into an LLM prompt (cost amplification, prompt injection surface
expansion) with zero guardrails.

This module enforces:
  - a maximum serialized payload size (bytes)
  - a maximum JSON nesting depth
  - a maximum number of keys/items at any single level
  - a maximum length for any individual string value

It intentionally does NOT enforce a fixed schema for the payload itself --
real-world webhook payloads (Datadog, PagerDuty, Airflow, etc.) vary
significantly in shape, and the WatcherAgent's job is precisely to
interpret arbitrary payloads. The guardrails here are about BOUNDING
untrusted input, not validating its business meaning.
"""

import json
from typing import Any

from fastapi import HTTPException

MAX_PAYLOAD_BYTES = 64 * 1024  # 64KB
MAX_JSON_DEPTH = 12
MAX_ITEMS_PER_LEVEL = 200
MAX_STRING_LENGTH = 8192


class WebhookPayloadTooLarge(Exception):
    pass


class WebhookPayloadMalformed(Exception):
    pass


def _check_depth_and_shape(value: Any, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise WebhookPayloadMalformed(f"Payload nesting exceeds maximum depth of {MAX_JSON_DEPTH}.")

    if isinstance(value, dict):
        if len(value) > MAX_ITEMS_PER_LEVEL:
            raise WebhookPayloadMalformed(
                f"Object has {len(value)} keys, exceeding the maximum of {MAX_ITEMS_PER_LEVEL} per level."
            )
        for v in value.values():
            _check_depth_and_shape(v, depth + 1)
    elif isinstance(value, list):
        if len(value) > MAX_ITEMS_PER_LEVEL:
            raise WebhookPayloadMalformed(
                f"Array has {len(value)} items, exceeding the maximum of {MAX_ITEMS_PER_LEVEL} per level."
            )
        for v in value:
            _check_depth_and_shape(v, depth + 1)
    elif isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH:
            raise WebhookPayloadMalformed(
                f"String value length {len(value)} exceeds the maximum of {MAX_STRING_LENGTH} characters."
            )


def validate_webhook_payload(payload: dict) -> None:
    """
    Raises HTTPException(413) if the payload is too large, or
    HTTPException(422) if it's malformed/too deeply nested/etc.
    Call this BEFORE passing the payload to any downstream LLM call.
    """
    try:
        serialized = json.dumps(payload)
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=422, detail=f"Payload is not valid JSON: {e}")

    size_bytes = len(serialized.encode("utf-8"))
    if size_bytes > MAX_PAYLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Webhook payload of {size_bytes} bytes exceeds the maximum allowed size of {MAX_PAYLOAD_BYTES} bytes.",
        )

    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Webhook payload must be a JSON object.")

    try:
        _check_depth_and_shape(payload)
    except WebhookPayloadMalformed as e:
        raise HTTPException(status_code=422, detail=str(e))
