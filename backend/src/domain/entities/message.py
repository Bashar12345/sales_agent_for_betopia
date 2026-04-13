# [OWNER: Niloy — P1 Conversation Engine]
"""Message — a single turn inside a Conversation.

Populated when the salesperson pastes the customer's message into the UI (P1 pipeline).
direction=in  → message came from the customer
direction=out → message sent by the salesperson (selected suggestion or manual)
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class MessageRole(StrEnum):
    CUSTOMER = "customer"
    SALESMAN = "salesman"
    SYSTEM = "system"        # Internal notes / auto-generated context


class MessageDirection(StrEnum):
    IN = "in"    # Customer → Salesperson
    OUT = "out"  # Salesperson → Customer


class Message(BaseModel):
    id: UUID
    conversation_id: UUID
    role: MessageRole
    direction: MessageDirection = MessageDirection.IN

    content: str
    created_at: datetime

    # Timestamp when the salesperson actually sent the reply (nullable until sent)
    sent_at: datetime | None = None

    # P1 intent classifier output for this message
    intent_label: str | None = None  # one of INTENT_CLASSES from settings

    # Which suggestion rank was selected (1-5); None if message was typed manually
    suggestion_selected_rank: int | None = None

    # Set when this message contributed to a proposal generation
    used_in_quotation: bool = False
