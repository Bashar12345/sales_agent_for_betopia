# [OWNER: Dev 1 — Data Foundation (P3)]
"""ILLMPort — abstract interface for LLM text generation (OpenAI / Anthropic).

Embedding is intentionally separated into IEmbeddingPort so the embedding
model can be swapped independently of the generation model.

Fallback chain (configured in settings.py):
  GPT-4.1  →  Claude Sonnet 4.6 (if GPT-4.1 exceeds 3 s)  →  vLLM in-house
"""

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
          - A list of LineItems (structured output — no regex parsing)
          - Executive summary / notes for the quotation document
        """

    @abstractmethod
    async def generate_suggestions(
        self,
        customer_message: str,
        intent_label: str,
        recent_messages: list[Message],
        similar_conversations: list[str],
        resources_context: list[str],
    ) -> list[dict]:
        """Return exactly 5 ranked suggestion dicts for the salesperson (P1 pipeline)."""

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Embed text using the configured embedding model (3072-d)."""
