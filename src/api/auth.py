import os
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

def require_role(required_role: str):
    """
    Dependency generator for RBAC.
    """
    async def role_checker(current_user: User = Depends(get_current_user)):
        if "admin" in current_user.roles:
            return current_user # Admins can access everything
        if required_role not in current_user.roles:
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return current_user
    return role_checker

# Mock Endpoint to generate a test token (for development only)
def get_mock_token(role: str = "admin"):
    access_token = create_access_token(
        data={
            "sub": "mock-user-123", 
            "email": "test@nemoguard.com", 
            "roles": [role],
            "tenant_id": "tenant_A",
            "workspace_id": "ws_alpha"
        },
        expires_delta=timedelta(days=1)
    )
    return access_token
