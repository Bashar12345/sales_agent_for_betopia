# [OWNER: Niloy — P1 Conversation Engine]
from uuid import UUID

from pydantic import BaseModel

from src.domain.entities.message import MessageRole


class CreateConversationDTO(BaseModel):
    lead_id: UUID
    agent_id: UUID


class AddMessageDTO(BaseModel):
    conversation_id: UUID
    role: MessageRole
    content: str
