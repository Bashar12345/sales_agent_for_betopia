from uuid import UUID

from pydantic import BaseModel

from src.domain.entities.quotation import LineItem


class GenerateQuotationDTO(BaseModel):
    """Trigger LLM-based quotation generation from a conversation."""
    conversation_id: UUID
    agent_id: UUID


class UpdateQuotationDTO(BaseModel):
    """Manual edits to a draft quotation before it is sent."""
    title: str | None = None
    line_items: list[LineItem] | None = None
    notes: str | None = None
    currency: str | None = None


class ExportQuotationDTO(BaseModel):
    quotation_id: UUID
