# [OWNER: Dev 1 — Data Foundation (P3)]
"""SQLAlchemy ORM models for Conversation and Message — PostgreSQL 17."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.entities.conversation import ConversationStatus
from src.domain.entities.message import MessageDirection, MessageRole
from src.infrastructure.db.base import Base
from src.infrastructure.db.models.mixins import TimestampMixin


class MessageModel(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    conversation_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=False),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        PgEnum("customer", "salesman", "system", name="messagerole", create_type=False),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    used_in_quotation: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(String(64))  # ISO 8601 string

    # P1 fields — added in v3.0
    direction: Mapped[str | None] = mapped_column(
        PgEnum("in", "out", name="messagedirection", create_type=False),
        nullable=True, default=MessageDirection.IN.value,
    )
    intent_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    suggestion_selected_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    conversation: Mapped["ConversationModel"] = relationship(
        "ConversationModel", back_populates="messages"
    )


class ConversationModel(TimestampMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    lead_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=False),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=False), ForeignKey("sales_agents.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        PgEnum("active", "closed", "quoted", name="conversationstatus", create_type=False),
        nullable=False, default=ConversationStatus.ACTIVE.value,
    )
    vector_id: Mapped[str | None] = mapped_column(String(64))

    lead: Mapped["LeadModel"] = relationship("LeadModel", back_populates="conversations")  # type: ignore[name-defined]
    messages: Mapped[list[MessageModel]] = relationship(
        "MessageModel",
        back_populates="conversation",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
