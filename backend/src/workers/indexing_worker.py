"""Background task: embed a conversation into ChromaDB.

Called after a conversation is closed/quoted so it becomes available
for future similarity matching when generating replies or quotations.
"""

import asyncio
import uuid

import structlog

from src.core.settings import settings
from src.infrastructure.clients.chromadb_client import ChromaDBClient
from src.infrastructure.db.repositories.conversation_repository_impl import (
    ConversationRepositoryImpl,
)
from src.infrastructure.db.session import AsyncSessionLocal
from src.workers.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(name="index_conversation", bind=True, max_retries=3)
def index_conversation(self, conversation_id: str) -> None:
    """Embed the full transcript of a conversation into ChromaDB."""
    async def _run() -> None:
        async with AsyncSessionLocal() as session:
            repo = ConversationRepositoryImpl(session)
            conv = await repo.get_by_id(uuid.UUID(conversation_id))
            if not conv:
                log.error("worker.conversation_not_found", conversation_id=conversation_id)
                return

            transcript = conv.get_transcript()
            vs = ChromaDBClient()
            await vs.upsert(
                collection=settings.CHROMA_COLLECTION_CONVERSATIONS,
                doc_id=conversation_id,
                text=transcript,
                metadata={
                    "lead_id": str(conv.lead_id),
                    "agent_id": str(conv.agent_id),
                    "status": conv.status.value,
                },
            )
            conv.vector_id = conversation_id
            await repo.update(conv)
            await session.commit()
            log.info("worker.conversation_indexed", conversation_id=conversation_id)

    try:
        asyncio.run(_run())
    except Exception as exc:
        log.error("worker.index_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)
