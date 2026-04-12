"""Abstract repository interface for Conversations (MySQL-backed)."""

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.conversation import Conversation


class IConversationRepository(ABC):
    @abstractmethod
    async def create(self, conversation: Conversation) -> Conversation: ...

    @abstractmethod
    async def get_by_id(self, conversation_id: UUID) -> Conversation | None: ...

    @abstractmethod
    async def get_by_lead_id(self, lead_id: UUID) -> list[Conversation]: ...

    @abstractmethod
    async def update(self, conversation: Conversation) -> Conversation: ...

    @abstractmethod
    async def delete(self, conversation_id: UUID) -> None: ...
