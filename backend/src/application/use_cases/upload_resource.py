# [OWNER: Asif — P2 Requirements Agent]
"""UploadResource — store a document and index it in ChromaDB.

Used by the developer/tester UI page where agents upload price lists,
service catalogues, or past conversations to build the knowledge base.
"""

import uuid
from datetime import datetime, timezone

from src.application.dto.resource_dto import UploadResourceDTO
from src.application.ports.vector_store_port import IVectorStorePort
from src.core.settings import settings
from src.domain.entities.resource import Resource
from src.domain.repositories.resource_repository import IResourceRepository


class UploadResourceUseCase:
    def __init__(
        self,
        resource_repo: IResourceRepository,
        vector_store: IVectorStorePort,
    ) -> None:
        self._resource_repo = resource_repo
        self._vs = vector_store

    async def execute(self, dto: UploadResourceDTO) -> Resource:
        now = datetime.now(timezone.utc)
        resource = Resource(
            id=uuid.uuid4(),
            name=dto.name,
            resource_type=dto.resource_type,
            content=dto.content,
            original_filename=dto.original_filename,
            uploaded_by_agent_id=dto.uploaded_by_agent_id,
            created_at=now,
        )
        resource = await self._resource_repo.create(resource)

        await self._vs.upsert(
            collection=settings.CHROMA_COLLECTION_RESOURCES,
            doc_id=str(resource.id),
            text=resource.content,
            metadata={
                "name": resource.name,
                "type": resource.resource_type.value,
                "agent_id": str(resource.uploaded_by_agent_id),
            },
        )
        resource.vector_id = str(resource.id)
        await self._resource_repo.create(resource)  # update is fine; repo upserts by id

        return resource
