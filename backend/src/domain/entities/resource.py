# [OWNER: Dev 3 — P2 Requirements Agent]
"""Resource — a document uploaded by a developer/agent for context.

Resources (price lists, service catalogues, past proposals) are embedded
into ChromaDB so the LLM can retrieve relevant context when generating
quotations or reply suggestions.
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class ResourceType(StrEnum):
    PRICE_LIST = "price_list"
    SERVICE_CATALOGUE = "service_catalogue"
    PAST_QUOTATION = "past_quotation"
    CONVERSATION_SAMPLE = "conversation_sample"
    OTHER = "other"


class Resource(BaseModel):
    id: UUID
    name: str
    resource_type: ResourceType
    # Raw text extracted from the uploaded file
    content: str
    # Original file stored on disk
    file_path: str | None = None
    original_filename: str | None = None
    # ChromaDB vector ID (set after successful embedding)
    vector_id: str | None = None
    uploaded_by_agent_id: UUID
    created_at: datetime
