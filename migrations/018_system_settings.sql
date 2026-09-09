-- System Settings: genuinely admin-editable configuration, replacing
-- hardcoded Python string constants for model selection so an admin can
-- change which AI model each agent tier uses (or add newly-supported
-- models, e.g. moonshotai/kimi-k3) WITHOUT a code change or redeploy.
--
-- Key-value store, one row per logical setting. `value_json` holds the
-- actual value as JSON so a single table can hold strings, numbers, or
-- structured objects (e.g. a model's required extra_body params) without
-- needing a new column per setting type.

CREATE TABLE IF NOT EXISTS system_setting (
    setting_key VARCHAR PRIMARY KEY,
    value_json VARCHAR NOT NULL,
    description VARCHAR,
    updated_by VARCHAR,
    updated_at VARCHAR NOT NULL
);

-- Seed the settings this deployment already effectively has (as hardcoded
-- Python defaults) so existing behavior is unchanged until an admin
-- explicitly edits something -- this migration does not silently alter
-- runtime behavior on its own.
INSERT INTO system_setting (setting_key, value_json, description, updated_by, updated_at)
VALUES
    (
        'model.super_tier',
        '{"model": "nvidia/nemotron-3-super-120b-a12b", "extra_body": {}}',
        'Fast-tier model used by Watcher Agent and Commander guidance-reaction calls.',
        'system',
        now()::text
    ),
    (
        'model.ultra_tier',
        '{"model": "nvidia/nemotron-3-ultra-550b-a55b", "extra_body": {"chat_template_kwargs": {"enable_thinking": true}, "reasoning_budget": 16384}}',
        'High-reasoning-tier model used by RCA Agent, Grounding Critic, and Commander Live ASK.',
        'system',
        now()::text
    ),
    (
        'model.fallback_tier',
        '{"model": "nvidia/nemotron-3-super-120b-a12b", "extra_body": {}}',
        'Fallback model automatically used if the ultra_tier model times out or errors.',
        'system',
        now()::text
    ),
    (
        'model.fallback_timeout_seconds',
        '45',
        'Seconds to wait for the ultra_tier model before falling back to model.fallback_tier.',
        'system',
        now()::text
    )
ON CONFLICT (setting_key) DO NOTHING;
