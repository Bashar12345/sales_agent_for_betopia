# [OWNER: Bashar — Frontend, Auth & DevOps]
"""SalesAgent — an internal user who handles leads and conversations.

Roles align with v3.0 RBAC model enforced in security.py:
  SALESPERSON   — day-to-day conversation handling, paste messages, select suggestions
  SALES_MANAGER — all of the above + see all agents' leads, approve proposals
  ADMIN         — full access including user management and system config
  READ_ONLY     — analytics dashboards, no write access
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, EmailStr

from src.core.security import Role


class AgentRole(StrEnum):
    SALESPERSON = Role.SALESPERSON
    SALES_MANAGER = Role.SALES_MANAGER
    ADMIN = Role.ADMIN
    READ_ONLY = Role.READ_ONLY


class SalesAgent(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    hashed_password: str
    role: AgentRole = AgentRole.SALESPERSON
    is_active: bool = True
    # Odoo user ID for future ERP sync
    odoo_user_id: int | None = None
    created_at: datetime
    updated_at: datetime
