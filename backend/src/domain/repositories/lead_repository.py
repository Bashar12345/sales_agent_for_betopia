"""Abstract repository interface for Leads (MySQL-backed)."""

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.lead import Lead, LeadStatus


class ILeadRepository(ABC):
    @abstractmethod
    async def create(self, lead: Lead) -> Lead: ...

    @abstractmethod
    async def get_by_id(self, lead_id: UUID) -> Lead | None: ...

    @abstractmethod
    async def get_by_fiverr_order_id(self, order_id: str) -> Lead | None: ...

    @abstractmethod
    async def list_all(self, limit: int = 50, offset: int = 0) -> list[Lead]: ...

    @abstractmethod
    async def list_by_status(self, status: LeadStatus) -> list[Lead]: ...

    @abstractmethod
    async def update(self, lead: Lead) -> Lead: ...

    @abstractmethod
    async def delete(self, lead_id: UUID) -> None: ...
