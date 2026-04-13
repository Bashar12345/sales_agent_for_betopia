# [OWNER: Dev 1 — Data Foundation (P3)]
"""SQLAlchemy ORM model for Lead — PostgreSQL 17."""

import uuid

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.entities.lead import LeadSource, LeadStatus
from src.infrastructure.db.base import Base
from src.infrastructure.db.models.mixins import TimestampMixin


class LeadModel(TimestampMixin, Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    fiverr_order_id: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    fiverr_buyer_username: Mapped[str | None] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    budget: Mapped[float | None] = mapped_column(Float)
    requirement_summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        PgEnum("new", "in_conversation", "quoted", "won", "lost",
               name="leadstatus", create_type=False),
        nullable=False, default=LeadStatus.NEW.value, index=True,
    )
    source: Mapped[str] = mapped_column(
        PgEnum("fiverr", "manual", name="leadsource", create_type=False),
        nullable=False, default=LeadSource.FIVERR.value,
    )
    assigned_agent_id: Mapped[str | None] = mapped_column(
        PGUUID(as_uuid=False), ForeignKey("sales_agents.id"), index=True
    )

    conversations: Mapped[list["ConversationModel"]] = relationship(  # type: ignore[name-defined]
        "ConversationModel", back_populates="lead", lazy="selectin"
    )
