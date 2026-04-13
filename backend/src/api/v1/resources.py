# [OWNER: Akash — P2 Requirements Agent]
"""Resource endpoints — developer/tester knowledge-base management.

Supports uploading .txt/.pdf/docx files or raw text. Each resource
is stored in MySQL and embedded into ChromaDB.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dto.resource_dto import UploadResourceDTO
from src.application.use_cases.upload_resource import UploadResourceUseCase
from src.domain.entities.resource import Resource, ResourceType
from src.infrastructure.clients.chromadb_client import ChromaDBClient
from src.infrastructure.db.repositories.resource_repository_impl import ResourceRepositoryImpl
from src.infrastructure.db.session import get_db

router = APIRouter(prefix="/resources", tags=["resources"])


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=Resource)
async def upload_resource(
    name: str = Form(...),
    resource_type: ResourceType = Form(...),
    uploaded_by_agent_id: uuid.UUID = Form(...),
    content: str | None = Form(None),
    file: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
) -> Resource:
    """
    Upload a resource. Provide either raw `content` text or a `file` upload.
    Accepts .txt files; for .pdf and .docx, extract text before uploading
    (a dedicated extraction endpoint will be added in a future iteration).
    """
    if content is None and file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either 'content' text or a 'file' upload",
        )

    text = content
    original_filename = None
    if file is not None:
        raw = await file.read()
        text = raw.decode("utf-8", errors="replace")
        original_filename = file.filename

    dto = UploadResourceDTO(
        name=name,
        resource_type=resource_type,
        content=text,  # type: ignore[arg-type]
        original_filename=original_filename,
        uploaded_by_agent_id=uploaded_by_agent_id,
    )
    use_case = UploadResourceUseCase(
        resource_repo=ResourceRepositoryImpl(db),
        vector_store=ChromaDBClient(),
    )
    return await use_case.execute(dto)


@router.get("/", response_model=list[Resource])
async def list_resources(
    resource_type: ResourceType | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[Resource]:
    repo = ResourceRepositoryImpl(db)
    if resource_type:
        return await repo.list_by_type(resource_type)
    return await repo.list_all()


@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(
    resource_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    repo = ResourceRepositoryImpl(db)
    vs = ChromaDBClient()
    resource = await repo.get_by_id(resource_id)
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    await repo.delete(resource_id)
    from src.core.settings import settings
    await vs.delete(settings.CHROMA_COLLECTION_RESOURCES, str(resource_id))
