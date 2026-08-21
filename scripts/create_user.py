#!/usr/bin/env python3
"""
Provision a real, credential-backed NemoGuard operator account.

This is how you create actual production sign-in accounts: it hashes the
given password with the same PBKDF2 scheme the API verifies against and
inserts (or updates) a row in `platform_user`. Once at least one active
account exists, the frontend's login screen automatically stops offering
"Demo Mode" / mock sign-in (see GET /api/v2/auth/config).

Usage:
    python scripts/create_user.py \
        --email commander@yourcompany.com \
        --password "a strong unique password" \
        --role commander \
        --name "Jane Doe"

Requires POSTGRES_URL (or defaults to the docker-compose value) and can be
run from the host if `psycopg2` + network access to postgres are available,
or via:
    docker compose exec api python scripts/create_user.py --email ... --password ...
"""
import argparse
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.store.postgres_database import PostgresDatabase
from src.api.auth import hash_password

# Full role set per docs/NemoGuard_Enterprise_Hardening_and_Productization_Build_Plan.md
# §11.2. Previously only {"commander", "admin", "viewer"} were provisionable
# here, meaning there was no way to actually create a real "operator",
# "approver", "auditor", or "service" account despite src/api/auth.py's
# require_role()/require_any_role() already enforcing all seven roles.
VALID_ROLES = {"viewer", "operator", "commander", "approver", "admin", "auditor", "service"}


def main():
    parser = argparse.ArgumentParser(description="Provision a real NemoGuard operator account.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--role", default="commander", choices=sorted(VALID_ROLES))
    parser.add_argument("--name", default=None, help="Display name (defaults to the email's local part).")
    parser.add_argument("--tenant-id", default="default_tenant")
    parser.add_argument("--workspace-id", default="default_workspace")
    args = parser.parse_args()

    email = args.email.strip().lower()
    display_name = args.name or email.split("@")[0]

    postgres_url = os.environ.get(
        "POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"
    )
    db = PostgresDatabase(postgres_url)
    db.apply_pending_migrations()  # ensures platform_user table exists

    password_hash = hash_password(args.password)
    user_id = f"USR-{uuid.uuid4().hex[:10]}"

    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO platform_user (user_id, email, password_hash, display_name, roles, tenant_id, workspace_id, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (email) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                display_name = EXCLUDED.display_name,
                roles = EXCLUDED.roles,
                tenant_id = EXCLUDED.tenant_id,
                workspace_id = EXCLUDED.workspace_id,
                is_active = TRUE
            """,
            (user_id, email, password_hash, display_name, [args.role], args.tenant_id, args.workspace_id),
        )

    print(f"Provisioned account for {email} with role '{args.role}'.")
    print("The login page will now require real credentials for this deployment.")


if __name__ == "__main__":
    main()
