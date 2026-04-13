# [OWNER: Dev 3 — P2 Requirements Agent]
from uuid import UUID

from pydantic import BaseModel

from src.domain.entities.resource import ResourceType


class UploadResourceDTO(BaseModel):
    name: str
    resource_type: ResourceType
    content: str              # Extracted text (caller handles file → text parsing)
    original_filename: str | None = None
    uploaded_by_agent_id: UUID
