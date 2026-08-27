-- WP-ORG-002 §4.19-4.22: Teams Incident Communications (Phase A -- outbound
-- webhook notifications driven by the same typed incident-update stream
-- used by Commander Pulse).
--
-- Per §4.21: "Do not store raw secrets in this table." The webhook URL
-- itself is never persisted here -- it is resolved at dispatch time from
-- an environment variable named TEAMS_WEBHOOK_URL_<route_id> (uppercased),
-- so this table only carries routing/policy metadata, never a credential.

CREATE TABLE IF NOT EXISTS teams_notification_route (
    route_id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    environment VARCHAR,           -- e.g. 'prod', 'staging', or NULL for any
    service_pattern VARCHAR,       -- substring/glob match against incident.service, or NULL for any
    severity_threshold VARCHAR,    -- minimum severity (SEV_1..SEV_4) that triggers this route, or NULL for any
    team_id VARCHAR,
    channel_id VARCHAR,
    delivery_mode VARCHAR NOT NULL DEFAULT 'WORKFLOWS_WEBHOOK',
    notify_on_json VARCHAR NOT NULL DEFAULT '[]',  -- allowlisted update_type values (see status_projector.py)
    created_by VARCHAR,
    created_at VARCHAR NOT NULL,
    updated_at VARCHAR NOT NULL
);

-- Durable delivery log -- lets an admin see what was actually sent/attempted
-- without needing to grep container logs, and gives NotificationDispatcher
-- an idempotency check so the same commander_status_update is never
-- delivered to the same route twice.
CREATE TABLE IF NOT EXISTS teams_notification_delivery (
    delivery_id VARCHAR PRIMARY KEY,
    route_id VARCHAR NOT NULL,
    incident_id VARCHAR NOT NULL,
    source_update_id VARCHAR,
    update_type VARCHAR NOT NULL,
    status VARCHAR NOT NULL,       -- SENT | FAILED | SKIPPED_NO_WEBHOOK_CONFIGURED
    error_message VARCHAR,
    created_at VARCHAR NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_teams_delivery_incident ON teams_notification_delivery(incident_id, created_at);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'teams_delivery_route_update_unique'
    ) THEN
        ALTER TABLE teams_notification_delivery
            ADD CONSTRAINT teams_delivery_route_update_unique UNIQUE (route_id, source_update_id);
    END IF;
END $$;
