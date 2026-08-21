import os
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from pydantic import BaseModel

SECRET_KEY = os.environ.get("JWT_SECRET")
if not SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET environment variable is not set. Refusing to start with an insecure default. "
        "Set JWT_SECRET in your .env file (see .env.example)."
    )
ALGORITHM = "HS256"
IS_DEV_ENV = os.environ.get("ENV", "production").lower() in ("development", "dev", "local")

security = HTTPBearer()

class User(BaseModel):
    user_id: str
    email: str
    roles: List[str]
    tenant_id: str
    workspace_id: str

class LoginRequest(BaseModel):
    email: str
    password: str

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Dependency to get the current authenticated user from the JWT token.
    In a real enterprise OIDC integration (Auth0/Okta), this would validate the token signature against the JWKS endpoint.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
            
        return User(
            user_id=user_id,
            email=payload.get("email", ""),
            roles=payload.get("roles", ["viewer"]),
            tenant_id=payload.get("tenant_id", "default_tenant"),
            workspace_id=payload.get("workspace_id", "default_workspace")
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ---------------------------------------------------------------------------
# Role hierarchy (build plan Priority 7 / spec §11.2).
#
# Minimum roles: viewer, operator, commander, approver, admin, auditor,
# service. Each role listed below inherits every permission of the roles
# in its "includes" set, matching the spec's additive definitions
# (e.g. "operator: viewer + trigger triage, add notes"). `admin` is a
# superset of every operational role (but NOT of `auditor`'s restriction
# against operational mutation, nor does it need to be -- admin already
# has broader access by design). `approver` and `auditor` are deliberately
# NOT included in this operational hierarchy: approval authority and
# audit-read authority are separate concerns from the
# viewer->operator->commander operational ladder, per the spec's role
# table, and must be granted explicitly.
# ---------------------------------------------------------------------------
_ROLE_HIERARCHY = {
    "viewer": {"viewer"},
    "operator": {"viewer", "operator"},
    "commander": {"viewer", "operator", "commander"},
    "approver": {"approver"},
    "auditor": {"auditor"},
    "admin": {"viewer", "operator", "commander", "approver", "auditor", "admin"},
    "service": {"service"},
}


def _effective_roles(user_roles: List[str]) -> set:
    effective = set()
    for r in user_roles:
        effective |= _ROLE_HIERARCHY.get(r, {r})
    return effective


def require_role(required_role: str):
    """
    Dependency generator for RBAC. Grants access if the user holds
    `required_role` directly, OR holds any role whose hierarchy (per
    _ROLE_HIERARCHY) includes `required_role` -- e.g. a `commander` token
    satisfies a `require_role("operator")` check, since commander is
    additive over operator per spec §11.2.
    """
    async def role_checker(current_user: User = Depends(get_current_user)):
        if required_role in _effective_roles(current_user.roles):
            return current_user
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return role_checker


def require_any_role(*acceptable_roles: str):
    """
    Like require_role, but grants access if the user's effective roles
    intersect ANY of the acceptable_roles -- for endpoints where multiple
    independent roles are each sufficient (e.g. approve_plan should accept
    either "approver" or "admin", which are not related by inheritance).
    """
    async def role_checker(current_user: User = Depends(get_current_user)):
        effective = _effective_roles(current_user.roles)
        if effective.intersection(acceptable_roles):
            return current_user
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return role_checker

# Mock Endpoint to generate a test token — only reachable when ENV is
# development/dev/local (enforced in main.py). Never usable in production.
def get_mock_token(role: str = "admin"):
    access_token = create_access_token(
        data={
            "sub": "mock-user-123", 
            "email": "test@nemoguard.com", 
            "roles": [role],
            # Previously hardcoded to "tenant_A"/"ws_alpha", which never
            # matches the "default_tenant" every demo/seed incident row
            # actually carries (see migrations/002_domain_model.sql's
            # column default) -- so once WP-002/WP-006's tenant scoping
            # was added, the mock-login demo flow started returning 404 for
            # every single incident sub-resource despite the incidents
            # genuinely existing. Align the mock token's tenant with the
            # actual default tenant used everywhere else so the dev-mode
            # demo flow keeps working.
            "tenant_id": "default_tenant",
            "workspace_id": "default_workspace"
        },
        expires_delta=timedelta(days=1)
    )
    return access_token


# ---------------------------------------------------------------------------
# Real credential-backed authentication (production login path).
#
# Passwords are never stored in plaintext. We hash with PBKDF2-HMAC-SHA256
# (via hashlib, no extra dependency needed) using a random per-user salt and
# a high iteration count, in the standard `pbkdf2_sha256$<iterations>$<salt>$<hash>`
# format so it's self-describing and can be re-parameterized later without a
# migration.
# ---------------------------------------------------------------------------

_PBKDF2_ITERATIONS = 260_000


def hash_password(plain_password: str) -> str:
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${derived.hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    try:
        algo, iterations_str, salt, hex_digest = stored_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iterations_str)
    except (ValueError, AttributeError):
        return False
    derived = hashlib.pbkdf2_hmac(
        "sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    return hmac.compare_digest(derived.hex(), hex_digest)


def issue_token_for_user(user_row: dict) -> str:
    """Builds a real, short-lived JWT for an authenticated platform_user row."""
    return create_access_token(
        data={
            "sub": user_row["user_id"],
            "email": user_row["email"],
            "roles": list(user_row.get("roles") or ["viewer"]),
            "tenant_id": user_row.get("tenant_id", "default_tenant"),
            "workspace_id": user_row.get("workspace_id", "default_workspace"),
        },
        expires_delta=timedelta(hours=8),
    )
