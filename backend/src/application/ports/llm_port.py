"""ILLMPort — abstract interface for any LLM provider (OpenAI / Anthropic)."""

from abc import ABC, abstractmethod

from src.domain.entities.message import Message
from src.domain.entities.quotation import LineItem


class ILLMPort(ABC):
    @abstractmethod
    async def generate_quotation_items(
        self,
        transcript: str,
        similar_quotations: list[str],
        resources_context: list[str],
    ) -> tuple[list[LineItem], str]:
        """
        Given a conversation transcript + retrieved context, return:
          - A list of LineItems
          - Notes / executive summary for the quotation
        """

    @abstractmethod
    async def suggest_replies(
        self,
        customer_message: str,
        recent_messages: list[Message],
        similar_conversations: list[str],
        resources_context: list[str],
    ) -> list[str]:
        """Return up to 3 reply candidates for the salesman."""

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Return a vector embedding for ChromaDB upsert."""
