# [OWNER: Akash — P2 Requirements Agent]
"""Abstract repository interface for Resources (MySQL-backed)."""

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.resource import Resource, ResourceType


class IResourceRepository(ABC):
    @abstractmethod
    async def create(self, resource: Resource) -> Resource: ...

    @abstractmethod
    async def get_by_id(self, resource_id: UUID) -> Resource | None: ...

    @abstractmethod
    async def list_by_type(self, resource_type: ResourceType) -> list[Resource]: ...

    @abstractmethod
    async def list_all(self, limit: int = 100) -> list[Resource]: ...

    @abstractmethod
    async def delete(self, resource_id: UUID) -> None: ...
