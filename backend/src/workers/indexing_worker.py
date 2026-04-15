# [OWNER: Dev 1 — Data Foundation (P3)]
"""Background task: embed a conversation into Qdrant (P3 indexing pipeline).

Called after a conversation is closed/quoted so its transcript becomes
available for future P1/P2 similarity matching.

Queue: p3-batch  (low priority — does not block the user-facing request)
"""

import asyncio
import uuid

import structlog

from src.core.settings import settings
from src.infrastructure.clients.llm_client import LLMClient
from src.infrastructure.clients.qdrant_client import QdrantVectorClient
from src.infrastructure.db.repositories.conversation_repository_impl import (
    ConversationRepositoryImpl,
)
from src.infrastructure.db.session import AsyncSessionLocal
from src.workers.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(name="index_conversation", bind=True, max_retries=3, queue="p3-batch")
def index_conversation(self, conversation_id: str) -> None:
    """Embed the full transcript of a conversation into Qdrant."""

    async def _run() -> None:
        async with AsyncSessionLocal() as session:
            repo = ConversationRepositoryImpl(session)
            conv = await repo.get_by_id(uuid.UUID(conversation_id))
            if not conv:
                log.error("worker.conversation_not_found", conversation_id=conversation_id)
                return

            transcript = conv.get_transcript()

            # Embed via LLMClient (text-embedding-3-large, 3072-dim)
            llm = LLMClient()
            vector = await llm.embed_text(transcript)

            # Upsert into Qdrant conversations collection
            vs = QdrantVectorClient()
            await vs.upsert(
                collection=settings.QDRANT_COLLECTION_CONVERSATIONS,
                doc_id=conversation_id,
                text=transcript,
                metadata={
                    "lead_id": str(conv.lead_id),
                    "agent_id": str(conv.agent_id),
                    "status": conv.status.value,
                },
                vector=vector,
            )

            conv.vector_id = conversation_id
            await repo.update(conv)
            await session.commit()
            log.info("worker.conversation_indexed", conversation_id=conversation_id)

    from src.infrastructure.db.session import engine as _engine  # noqa: PLC0415

    async def _run_and_dispose() -> None:
        try:
            await _run()
        finally:
            await _engine.dispose()

    try:
        asyncio.run(_run_and_dispose())
    except Exception as exc:
        log.error("worker.index_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="re_embed_collection", bind=True, max_retries=2, queue="p3-batch")
def re_embed_collection(self, collection: str) -> None:
    """Re-embed an entire Qdrant collection (e.g. after model upgrade).

    Iterates all documents in the named PostgreSQL table, re-embeds, and
    bulk-upserts into the corresponding Qdrant collection.
    """
    log.info("worker.re_embed_started", collection=collection)
    # Implementation: query all rows with vector_id IS NOT NULL, re-embed, upsert.
    # Filled in by Dev 1 during sprint 1 P3 work.
    raise NotImplementedError("re_embed_collection not yet implemented")
