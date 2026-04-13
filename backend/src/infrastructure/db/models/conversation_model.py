# [OWNER: Zohra — Data Foundation (P3)]
"""SQLAlchemy ORM models for Conversation and Message — PostgreSQL 17."""

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.entities.conversation import ConversationStatus
from src.domain.entities.message import MessageRole
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
    role: Mapped[str] = mapped_column(Enum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    used_in_quotation: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(String(64))  # ISO 8601 string

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
        Enum(ConversationStatus), nullable=False, default=ConversationStatus.ACTIVE
    )
    vector_id: Mapped[str | None] = mapped_column(String(64))

    lead: Mapped["LeadModel"] = relationship("LeadModel", back_populates="conversations")  # type: ignore[name-defined]
    messages: Mapped[list[MessageModel]] = relationship(
        "MessageModel",
        back_populates="conversation",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
