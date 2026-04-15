# [OWNER: Bashar — Frontend, Auth & DevOps]
"""Auth endpoints — login, token refresh, and current-agent profile.

RS256 (asymmetric) tokens only — never HS256.
  POST /auth/login    — exchange email + password for an access token
  POST /auth/refresh  — exchange a refresh token for a new access token
  GET  /auth/me       — return the calling agent's profile
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import (
    Role,
    create_access_token,
    decode_token,
    get_current_agent,
    verify_password,
)
from src.domain.entities.sales_agent import AgentRole
from src.infrastructure.db.models.sales_agent_model import SalesAgentModel
from src.infrastructure.db.session import get_db

router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    # Field name matches the spec — value must be a refresh token (not an access token)
    access_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SalesAgentResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: AgentRole
    is_active: bool
    odoo_user_id: int | None = None
    created_at: datetime
    updated_at: datetime


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _get_agent_by_email(db: AsyncSession, email: str) -> SalesAgentModel | None:
    result = await db.execute(
        select(SalesAgentModel).where(SalesAgentModel.email == email)
    )
    return result.scalar_one_or_none()


async def _get_agent_by_id(db: AsyncSession, agent_id: str) -> SalesAgentModel | None:
    result = await db.execute(
        select(SalesAgentModel).where(SalesAgentModel.id == agent_id)
    )
    return result.scalar_one_or_none()


# ── POST /login ───────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    agent = await _get_agent_by_email(db, str(body.email))
    if not agent or not verify_password(body.password, agent.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not agent.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )
    token = create_access_token(subject=agent.id, role=Role(agent.role))
    return TokenResponse(access_token=token)


# ── POST /refresh ─────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest) -> TokenResponse:
    try:
        payload = decode_token(body.access_token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("token_type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provided token is not a refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    subject: str | None = payload.get("sub")
    role_str: str | None = payload.get("role")
    if not subject or not role_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required claims",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        role = Role(role_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unrecognised role in token",
        ) from exc

    token = create_access_token(subject=subject, role=role)
    return TokenResponse(access_token=token)


# ── GET /me ───────────────────────────────────────────────────────────────────

@router.get("/me", response_model=SalesAgentResponse)
async def me(
    claims: dict[str, Any] = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> SalesAgentResponse:
    agent_id: str | None = claims.get("sub")
    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )

    agent = await _get_agent_by_id(db, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent not found",
        )
    if not agent.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    return SalesAgentResponse(
        id=agent.id,
        name=agent.name,
        email=agent.email,
        role=AgentRole(agent.role),
        is_active=agent.is_active,
        odoo_user_id=agent.odoo_user_id,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )