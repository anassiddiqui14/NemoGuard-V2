"""
System Settings service -- genuinely admin-editable configuration,
replacing hardcoded Python string constants for AI model selection.

User request: "i should be able to change settings whenever needed from
admin console." Backed by the system_setting table (migrations/018).

Pattern mirrors src/capabilities/policy.py's reload_policy_config():
settings are cached in-process after first load (so hot-path agent calls
don't hit the DB on every single LLM call), and an admin action can force
a live reload, with no process restart required.
"""
import json
import os
import threading
from typing import Any, Dict, Optional

from src.store.postgres_database import PostgresDatabase

_cache: Optional[Dict[str, Any]] = None
_cache_lock = threading.Lock()

# Hardcoded fallback defaults -- used ONLY if the system_setting table is
# somehow empty/unreachable (e.g. migration hasn't run yet in some
# environment), so a settings-service outage never fully breaks agent
# calls. These mirror the exact values the codebase used before this
# settings system existed.
_DEFAULTS: Dict[str, Any] = {
    "model.super_tier": {"model": "nvidia/nemotron-3-super-120b-a12b", "extra_body": {}},
    "model.ultra_tier": {
        "model": "nvidia/nemotron-3-ultra-550b-a55b",
        "extra_body": {"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 16384},
    },
    "model.fallback_tier": {"model": "nvidia/nemotron-3-super-120b-a12b", "extra_body": {}},
    "model.fallback_timeout_seconds": 45,
}

# Models known to work against the same integrate.api.nvidia.com endpoint
# this deployment already calls, for the admin UI's model picker.
# Verified live (2026-09-09): moonshotai/kimi-k3 requires reasoning_effort
# in extra_body and a generous max_tokens budget -- without it, it can
# exhaust its entire token budget on internal reasoning and return an
# EMPTY content string (confirmed live: a 20-token budget produced
# content=None; raising to 500 tokens + reasoning_effort="low" produced
# real content). This is why extra_body is part of each model's config,
# not a single global constant -- different model families need
# different invocation parameters.
KNOWN_MODELS = [
    {"model": "nvidia/nemotron-3-ultra-550b-a55b", "label": "Nemotron 3 Ultra 550B (highest reasoning, slowest)", "extra_body": {"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 16384}},
    {"model": "nvidia/nemotron-3-super-120b-a12b", "label": "Nemotron 3 Super 120B (fast, lower reasoning)", "extra_body": {}},
    {"model": "moonshotai/kimi-k3", "label": "Kimi K3 (Moonshot AI, via NVIDIA endpoint)", "extra_body": {"reasoning_effort": "low"}},
]


def _get_db() -> PostgresDatabase:
    return PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))


def _load_from_db() -> Dict[str, Any]:
    db = _get_db()
    result: Dict[str, Any] = dict(_DEFAULTS)
    try:
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT setting_key, value_json FROM system_setting")
            for key, value_json in cursor.fetchall():
                try:
                    result[key] = json.loads(value_json)
                except Exception:
                    # A malformed row should never take down agent calls --
                    # fall back to the default for that specific key only.
                    pass
    except Exception as e:
        print(f"[settings_service] Could not load system_setting table, using hardcoded defaults: {e}")
    return result


def get_setting(key: str) -> Any:
    """Returns the current value for `key`, loading+caching from the
    database on first call. Thread-safe."""
    global _cache
    if _cache is None:
        with _cache_lock:
            if _cache is None:
                _cache = _load_from_db()
    return _cache.get(key, _DEFAULTS.get(key))


def reload_settings() -> Dict[str, Any]:
    """Forces a fresh read from the database, discarding the in-process
    cache -- the live-reload half of "change settings whenever needed
    from admin console" (mirrors capabilities/policy.py's
    reload_policy_config())."""
    global _cache
    with _cache_lock:
        _cache = _load_from_db()
    return _cache


def list_settings() -> Dict[str, Any]:
    """Returns every currently-effective setting (for the admin UI)."""
    global _cache
    if _cache is None:
        with _cache_lock:
            if _cache is None:
                _cache = _load_from_db()
    return dict(_cache)


def update_setting(key: str, value: Any, updated_by: str) -> None:
    """Persists a new value for `key` and immediately reloads the
    in-process cache, so the change takes effect on the very next agent
    call -- no restart, no delay."""
    import datetime
    db = _get_db()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    value_json = json.dumps(value)
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO system_setting (setting_key, value_json, updated_by, updated_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (setting_key) DO UPDATE SET value_json = %s, updated_by = %s, updated_at = %s
            """,
            (key, value_json, updated_by, now, value_json, updated_by, now),
        )
    reload_settings()
