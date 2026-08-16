-- Real credential-backed users for production authentication.
-- Replaces the mock-login-only flow: operators now sign in with an email
-- and a password that is verified against a securely hashed value stored
-- here, and the JWT issued on successful login carries THIS user's real
-- roles/tenant/workspace rather than whatever role was picked in a demo
-- dropdown.
CREATE TABLE IF NOT EXISTS platform_user (
    user_id         TEXT PRIMARY KEY,
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    display_name    TEXT,
    roles           TEXT[] NOT NULL DEFAULT ARRAY['viewer']::TEXT[],
    tenant_id       TEXT NOT NULL DEFAULT 'default_tenant',
    workspace_id    TEXT NOT NULL DEFAULT 'default_workspace',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_platform_user_email ON platform_user (email);
