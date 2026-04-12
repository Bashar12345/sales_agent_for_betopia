"""SQLAlchemy ORM model for SalesAgent."""

import uuid

from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.sales_agent import AgentRole
from src.infrastructure.db.base import Base
from src.infrastructure.db.models.mixins import TimestampMixin


class SalesAgentModel(TimestampMixin, Base):
    __tablename__ = "sales_agents"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum(AgentRole), nullable=False, default=AgentRole.AGENT
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    odoo_user_id: Mapped[int | None] = mapped_column(Integer)
