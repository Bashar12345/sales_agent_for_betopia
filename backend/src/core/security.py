"""JWT RS256 token helpers, password hashing, and RBAC role enforcement.

Uses asymmetric RS256 (RSA-2048) — private key signs, public key verifies.
Generate keys:
    openssl genrsa -out certs/private.pem 2048
    openssl rsa -in certs/private.pem -pubout -out certs/public.pem
"""

from datetime import datetime, timedelta, timezone
from enum import StrEnum
from functools import wraps
from typing import Any, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from src.core.exceptions import UnauthorizedError
from src.core.settings import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_bearer = HTTPBearer()

ALGORITHM = "RS256"


class Role(StrEnum):
    SALESPERSON = "SALESPERSON"
    SALES_MANAGER = "SALES_MANAGER"
    ADMIN = "ADMIN"
    READ_ONLY = "READ_ONLY"


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ── Token creation ────────────────────────────────────────────────────────────

def create_access_token(
    subject: str,
    role: Role,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role.value,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "iss": settings.APP_NAME,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_PRIVATE_KEY, algorithm=ALGORITHM)


def create_refresh_token(subject: str, role: Role) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role.value,
        "exp": expire,
        "token_type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_PRIVATE_KEY, algorithm=ALGORITHM)


# ── Token decoding ────────────────────────────────────────────────────────────

def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify RS256 JWT. Raises JWTError on failure."""
    return jwt.decode(token, settings.JWT_PUBLIC_KEY, algorithms=[ALGORITHM])


def get_subject(token: str) -> str:
    """Return the subject claim (agent_id) or raise JWTError."""
    payload = decode_token(token)
    sub: str | None = payload.get("sub")
    if sub is None:
        raise JWTError("Token missing subject")
    return sub


# ── FastAPI dependency: current agent ────────────────────────────────────────

def get_current_agent(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict[str, Any]:
    """FastAPI dependency — extracts and validates the JWT from Bearer header."""
    try:
        return decode_token(credentials.credentials)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ── RBAC decorators ───────────────────────────────────────────────────────────

def require_roles(*allowed: Role) -> Callable[..., Any]:
    """FastAPI dependency factory — enforces role-based access.

    Usage:
        @router.get("/admin/users")
        async def list_users(agent=Depends(require_roles(Role.ADMIN))):
            ...
    """
    def dependency(agent: dict[str, Any] = Depends(get_current_agent)) -> dict[str, Any]:
        role = agent.get("role", "")
        if role not in {r.value for r in allowed}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' is not permitted for this action.",
            )
        return agent
    return dependency