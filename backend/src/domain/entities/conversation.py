"""Conversation — the full thread between a salesman and a lead."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

from src.domain.entities.message import Message


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"
    QUOTED = "quoted"        # A quotation was generated from this conversation


class Conversation(BaseModel):
    id: UUID
    lead_id: UUID
    agent_id: UUID
    status: ConversationStatus = ConversationStatus.ACTIVE
    messages: list[Message] = []
    # ChromaDB vector ID pointing to this conversation's embedding
    vector_id: str | None = None
    created_at: datetime
    updated_at: datetime

    def get_transcript(self) -> str:
        """Return a plain-text transcript ordered by creation time."""
        lines = [
            f"[{m.role.upper()}]: {m.content}"
            for m in sorted(self.messages, key=lambda x: x.created_at)
        ]
        return "\n".join(lines)
