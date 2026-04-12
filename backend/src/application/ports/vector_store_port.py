"""IVectorStorePort — abstract interface for ChromaDB vector operations."""

from abc import ABC, abstractmethod


class IVectorStorePort(ABC):
    @abstractmethod
    async def upsert(
        self,
        collection: str,
        doc_id: str,
        text: str,
        metadata: dict,
    ) -> None:
        """Embed text and upsert into the named collection."""

    @abstractmethod
    async def query_similar(
        self,
        collection: str,
        query_text: str,
        n_results: int = 5,
    ) -> list[dict]:
        """
        Return up to n_results similar documents.
        Each dict has keys: id, text, metadata, distance.
        """

    @abstractmethod
    async def delete(self, collection: str, doc_id: str) -> None:
        """Remove a document from the collection."""
