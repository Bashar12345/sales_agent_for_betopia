# [OWNER: Zohra — Data Foundation (P3)]
"""IVectorStorePort — abstract interface for Qdrant vector operations.

Qdrant requires pre-computed vectors — callers must embed text first via
IEmbeddingPort before calling upsert or query_similar.
"""

from abc import ABC, abstractmethod
from typing import Any


class IVectorStorePort(ABC):
    @abstractmethod
    async def upsert(
        self,
        collection: str,
        doc_id: str,
        text: str,
        metadata: dict[str, Any],
        vector: list[float],
    ) -> None:
        """Upsert a pre-embedded vector into the named collection."""

    @abstractmethod
    async def query_similar(
        self,
        collection: str,
        query_vector: list[float],
        n_results: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return up to n_results semantically similar documents.
        Each dict has keys: id, score, text, metadata.
        Optional filters: e.g. {"lead_id": "uuid-str"}.
        """

    @abstractmethod
    async def delete(self, collection: str, doc_id: str) -> None:
        """Remove a document from the collection."""