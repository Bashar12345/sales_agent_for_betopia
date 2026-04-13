# [OWNER: Dev 1 — Data Foundation (P3)]
"""IEmbeddingPort — abstract interface for text embedding.

Decoupled from ILLMPort so the embedding model can be swapped independently
(e.g. replace text-embedding-3-large with a fine-tuned model without
touching the generation pipeline).

Model: text-embedding-3-large → 3072-dim vectors (set in settings.py).
"""

from abc import ABC, abstractmethod


class IEmbeddingPort(ABC):
    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Return a 3072-dim vector for a single text string."""

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return 3072-dim vectors for a batch of texts (for bulk indexing)."""