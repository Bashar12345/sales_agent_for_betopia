"""Qdrant vector store client — implements IVectorStorePort.

Collections (3):
  conversations  — full conversation transcripts (P1 similarity)
  requirements   — extracted requirements docs (P2 matching)
  pricing        — past quotation line items (P2 cost estimation)

Index config:
  HNSW: m=16, ef_construct=200
  Scalar quantisation: INT8 — halves memory while keeping ~98% recall
  Vector size: 3072 (text-embedding-3-large)

Clients are initialized once at startup (singleton via dependency injection).
"""

from typing import Any

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    Filter,
    FieldCondition,
    MatchValue,
    HnswConfigDiff,
    PointStruct,
    QuantizationConfig,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    VectorParams,
)

from src.application.ports.vector_store_port import IVectorStorePort
from src.core.exceptions import VectorStoreError
from src.core.settings import settings

log = structlog.get_logger()

_VECTOR_SIZE = settings.EMBEDDING_DIMENSIONS  # 3072

_HNSW_CONFIG = HnswConfigDiff(
    m=settings.QDRANT_HNSW_M,
    ef_construct=settings.QDRANT_HNSW_EF_CONSTRUCT,
)

_QUANTIZATION_CONFIG = QuantizationConfig(
    scalar=ScalarQuantization(
        scalar=ScalarQuantizationConfig(
            type=ScalarType.INT8,
            always_ram=True,   # keep quantised vectors in RAM for low latency
        )
    )
)

_COLLECTIONS = [
    settings.QDRANT_COLLECTION_CONVERSATIONS,
    settings.QDRANT_COLLECTION_REQUIREMENTS,
    settings.QDRANT_COLLECTION_PRICING,
]


class QdrantVectorClient(IVectorStorePort):
    def __init__(self) -> None:
        self._client = AsyncQdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            api_key=settings.QDRANT_API_KEY or None,
            prefer_grpc=True,   # gRPC is ~2× faster than REST for batch ops
        )

    async def ensure_collections(self) -> None:
        """Create collections with HNSW + scalar quantisation if they don't exist.

        Called once during application startup.
        """
        existing = {c.name for c in await self._client.get_collections()}
        for name in _COLLECTIONS:
            if name not in existing:
                await self._client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(
                        size=_VECTOR_SIZE,
                        distance=Distance.COSINE,
                        hnsw_config=_HNSW_CONFIG,
                    ),
                    quantization_config=_QUANTIZATION_CONFIG,
                )
                log.info("qdrant.collection_created", collection=name)

    async def upsert(
        self,
        collection: str,
        doc_id: str,
        text: str,
        metadata: dict[str, Any],
        vector: list[float] | None = None,
    ) -> None:
        """Upsert a point.  Caller must pass a pre-computed vector or embed_text first."""
        if vector is None:
            raise VectorStoreError("vector is required for Qdrant upsert")
        try:
            point = PointStruct(
                id=doc_id,
                vector=vector,
                payload={"text": text, **metadata},
            )
            await self._client.upsert(collection_name=collection, points=[point])
        except Exception as exc:
            log.error("qdrant.upsert_failed", collection=collection, error=str(exc))
            raise VectorStoreError(f"Qdrant upsert failed: {exc}") from exc

    async def query_similar(
        self,
        collection: str,
        query_vector: list[float],
        n_results: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return up to n_results semantically similar points.

        Optional filters: e.g. {"lead_id": "uuid-str"} — translated to
        Qdrant payload filters for efficient pre-filtering.
        """
        qdrant_filter: Filter | None = None
        if filters:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filters.items()
            ]
            qdrant_filter = Filter(must=conditions)

        try:
            hits = await self._client.search(
                collection_name=collection,
                query_vector=query_vector,
                limit=n_results,
                query_filter=qdrant_filter,
                with_payload=True,
            )
            return [
                {
                    "id": str(hit.id),
                    "score": hit.score,
                    "text": hit.payload.get("text", "") if hit.payload else "",
                    "metadata": {
                        k: v
                        for k, v in (hit.payload or {}).items()
                        if k != "text"
                    },
                }
                for hit in hits
            ]
        except Exception as exc:
            log.error("qdrant.query_failed", collection=collection, error=str(exc))
            raise VectorStoreError(f"Qdrant query failed: {exc}") from exc

    async def delete(self, collection: str, doc_id: str) -> None:
        try:
            await self._client.delete(
                collection_name=collection,
                points_selector=[doc_id],
            )
        except Exception as exc:
            log.error("qdrant.delete_failed", collection=collection, doc_id=doc_id)
            raise VectorStoreError(f"Qdrant delete failed: {exc}") from exc
