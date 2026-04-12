from uuid import UUID

from pydantic import BaseModel


class SuggestRepliesDTO(BaseModel):
    """Input for the reply-suggestion endpoint (salesman tool page)."""
    # Optionally link to an existing conversation for full context
    conversation_id: UUID | None = None
    # The raw customer message to respond to (required)
    customer_message: str


class ReplySuggestionsResponseDTO(BaseModel):
    suggestions: list[str]
    conversation_id: UUID | None = None
