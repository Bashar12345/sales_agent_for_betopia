# [OWNER: Dev 1 — Data Foundation (P3)]
"""SQLAlchemy ORM model for SalesAgent — PostgreSQL 17."""

import uuid

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.sales_agent import AgentRole
from src.infrastructure.db.base import Base
from src.infrastructure.db.models.mixins import TimestampMixin


class SalesAgentModel(TimestampMixin, Base):
    __tablename__ = "sales_agents"

    id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        PgEnum("SALESPERSON", "SALES_MANAGER", "ADMIN", "READ_ONLY",
               name="agentrole", create_type=False),
        nullable=False, default=AgentRole.SALESPERSON.value,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    odoo_user_id: Mapped[int | None] = mapped_column(Integer)
