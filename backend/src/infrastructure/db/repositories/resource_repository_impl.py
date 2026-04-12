"""MySQL implementation of IResourceRepository."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.resource import Resource, ResourceType
from src.domain.repositories.resource_repository import IResourceRepository
from src.infrastructure.db.models.resource_model import ResourceModel


def _to_entity(m: ResourceModel) -> Resource:
    return Resource(
        id=uuid.UUID(m.id),
        name=m.name,
        resource_type=ResourceType(m.resource_type),
        content=m.content,
        file_path=m.file_path,
        original_filename=m.original_filename,
        vector_id=m.vector_id,
        uploaded_by_agent_id=uuid.UUID(m.uploaded_by_agent_id),
        created_at=m.created_at,
    )


class ResourceRepositoryImpl(IResourceRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, resource: Resource) -> Resource:
        # Upsert by id
        result = await self._session.execute(
            select(ResourceModel).where(ResourceModel.id == str(resource.id))
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.vector_id = resource.vector_id
            existing.file_path = resource.file_path
        else:
            model = ResourceModel(
                id=str(resource.id),
                name=resource.name,
                resource_type=resource.resource_type.value,
                content=resource.content,
                file_path=resource.file_path,
                original_filename=resource.original_filename,
                vector_id=resource.vector_id,
                uploaded_by_agent_id=str(resource.uploaded_by_agent_id),
                created_at=resource.created_at,
                updated_at=resource.created_at,
            )
            self._session.add(model)
        await self._session.flush()
        return resource

    async def get_by_id(self, resource_id: uuid.UUID) -> Resource | None:
        result = await self._session.execute(
            select(ResourceModel).where(ResourceModel.id == str(resource_id))
        )
        m = result.scalar_one_or_none()
        return _to_entity(m) if m else None

    async def list_by_type(self, resource_type: ResourceType) -> list[Resource]:
        result = await self._session.execute(
            select(ResourceModel).where(ResourceModel.resource_type == resource_type.value)
        )
        return [_to_entity(m) for m in result.scalars().all()]

    async def list_all(self, limit: int = 100) -> list[Resource]:
        result = await self._session.execute(
            select(ResourceModel).order_by(ResourceModel.created_at.desc()).limit(limit)
        )
        return [_to_entity(m) for m in result.scalars().all()]

    async def delete(self, resource_id: uuid.UUID) -> None:
        result = await self._session.execute(
            select(ResourceModel).where(ResourceModel.id == str(resource_id))
        )
        m = result.scalar_one_or_none()
        if m:
            await self._session.delete(m)
            await self._session.flush()
