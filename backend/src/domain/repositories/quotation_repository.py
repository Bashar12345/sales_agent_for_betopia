# [OWNER: Dev 3 — P2 Requirements Agent]
"""Abstract repository interface for Quotations (MySQL-backed)."""

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.quotation import Quotation


class IQuotationRepository(ABC):
    @abstractmethod
    async def create(self, quotation: Quotation) -> Quotation: ...

    @abstractmethod
    async def get_by_id(self, quotation_id: UUID) -> Quotation | None: ...

    @abstractmethod
    async def get_by_conversation_id(self, conversation_id: UUID) -> list[Quotation]: ...

    @abstractmethod
    async def get_by_lead_id(self, lead_id: UUID) -> list[Quotation]: ...

    @abstractmethod
    async def update(self, quotation: Quotation) -> Quotation: ...
