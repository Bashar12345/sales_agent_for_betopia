# [OWNER: Dev 2 — P1 Conversation Engine]
"""P1 Suggestion Pipeline — Celery background worker.

Triggered by: input.py calls generate_p1_suggestions.delay(message_id, conversation_id, lead_id)

Pipeline steps:
  1. Load message + conversation history from DB
  2. vLLM: classify_intent (~$0 cost, ~5 ms)
  3. Embed customer message — Redis cache (24h TTL) before hitting OpenAI
  4. Qdrant: query_similar("conversations", won_only=True) → past examples
  5. Qdrant: query_similar("pricing") → pricing context hints
  6. LLMClient.generate_suggestions() — GPT-4.1 → Claude Sonnet 4.6 → vLLM fallback
  7. vLLM: validate_tone() per suggestion — non-blocking (advisory only)
  8. [STUB] DB: persist SuggestionModel — uncomment when Dev 1 delivers SuggestionModel
  9. Redis: cache suggestions by lead_id (5 min TTL) for polling + WebSocket
  10. NATS: emit betopia.sales.suggestions.ready → WebSocket ws.py picks this up

Retry policy: max 3 retries, 60 s countdown.
Queue: "p1" — separate from p3-batch to keep high-priority tasks fast.
"""

import asyncio
import uuid

import structlog

from src.core.settings import settings
from src.infrastructure.clients.llm_client import LLMClient
from src.infrastructure.clients.nats_client import NATSClient
from src.infrastructure.clients.qdrant_client import QdrantVectorClient
from src.infrastructure.clients.redis_cache_client import RedisCacheClient
from src.infrastructure.clients.vllm_client import VLLMClient
from src.infrastructure.db.repositories.conversation_repository_impl import (
    ConversationRepositoryImpl,
)
from src.infrastructure.db.session import AsyncSessionLocal
from src.workers.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(name="generate_p1_suggestions", bind=True, max_retries=3, queue="p1")
def generate_p1_suggestions(
    self,
    message_id: str,
    conversation_id: str,
    lead_id: str,
) -> None:
    """Run the full P1 suggestion pipeline for a single customer message.

    All arguments are plain strings (UUID str) for Celery JSON serialisation.
    """

    async def _run() -> None:
        # ── 1. Load conversation + message from DB ────────────────────────────
        async with AsyncSessionLocal() as session:
            repo = ConversationRepositoryImpl(session)
            conv = await repo.get_by_id(uuid.UUID(conversation_id))

        if conv is None:
            log.error(
                "p1.conversation_not_found",
                conversation_id=conversation_id,
                lead_id=lead_id,
            )
            return

        # Find the specific message that triggered this pipeline run
        target = next(
            (m for m in conv.messages if str(m.id) == message_id),
            None,
        )
        if target is None:
            log.error(
                "p1.message_not_found",
                message_id=message_id,
                conversation_id=conversation_id,
            )
            return

        customer_message = target.content
        # Last 10 messages give the LLM enough context without blowing the prompt
        recent_messages = conv.messages[-10:]

        log.info(
            "p1.started",
            message_id=message_id,
            lead_id=lead_id,
            preview=customer_message[:80],
        )

        # ── 2. Intent classification (vLLM — near-zero cost) ──────────────────
        vllm = VLLMClient()
        intent_label = await vllm.classify_intent(customer_message)
        # vllm.classify_intent() already returns "new_inquiry" on failure — safe
        log.info("p1.intent", intent=intent_label)

        # ── 3. Embed customer message (Redis cache first) ──────────────────────
        cache = RedisCacheClient()
        llm = LLMClient()

        vector = await cache.get_embedding(customer_message)
        if vector is None:
            vector = await llm.embed_text(customer_message)  # raises LLMError on failure
            await cache.set_embedding(customer_message, vector)

        # ── 4. Qdrant: find similar past customer messages (won deals only) ────
        qdrant = QdrantVectorClient()
        try:
            similar_hits = await qdrant.query_similar(
                collection=settings.QDRANT_COLLECTION_CONVERSATIONS,
                query_vector=vector,
                n_results=5,
                filters={"outcome": "won"},
            )
            # Each hit's "text" is pre-formatted as:
            # "Customer (intent): ...\nAgent (strategy): ..."
            # This flows directly into the {{ similar_conversations }} slot
            # in v1_suggestion_prompt.yaml
            similar_conversations = [
                hit["text"] for hit in similar_hits if hit.get("text")
            ]
        except Exception as exc:
            log.warning("p1.qdrant_conversations_failed", error=str(exc))
            similar_conversations = []  # non-fatal — degrade gracefully

        # ── 5. Qdrant: pricing context (empty if collection not seeded yet) ────
        try:
            pricing_hits = await qdrant.query_similar(
                collection=settings.QDRANT_COLLECTION_PRICING,
                query_vector=vector,
                n_results=3,
            )
            resources_context = [
                hit["text"] for hit in pricing_hits if hit.get("text")
            ]
        except Exception:
            resources_context = []  # non-fatal

        # ── 6. Generate 5 suggestions via fallback chain ───────────────────────
        # LLMClient handles: GPT-4.1 (3s timeout) → Claude Sonnet 4.6 → vLLM
        suggestions = await llm.generate_suggestions(
            customer_message=customer_message,
            intent_label=intent_label,
            recent_messages=recent_messages,
            similar_conversations=similar_conversations,
            resources_context=resources_context,
        )

        log.info(
            "p1.suggestions_generated",
            count=len(suggestions),
            lead_id=lead_id,
            generated_by=suggestions[0].get("generated_by") if suggestions else "unknown",
        )

        # ── 7. Tone validation per suggestion (advisory — never blocks) ────────
        for suggestion in suggestions:
            try:
                tone_result = await vllm.validate_tone(suggestion.get("full_text", ""))
                if not tone_result.get("appropriate", True):
                    log.warning(
                        "p1.tone_flagged",
                        rank=suggestion.get("rank"),
                        reason=tone_result.get("reason"),
                    )
            except Exception:
                pass  # tone validation failure is never a blocker

        # ── 8. DB persistence ─────────────────────────────────────────────────
        from src.infrastructure.db.repositories.suggestion_repository_impl import (
            SuggestionRepositoryImpl,
        )
        async with AsyncSessionLocal() as session:
            suggestion_repo = SuggestionRepositoryImpl(session)
            await suggestion_repo.bulk_create(
                suggestions=suggestions,
                message_id=uuid.UUID(message_id),
                conversation_id=uuid.UUID(conversation_id),
                lead_id=uuid.UUID(lead_id),
                intent_label=intent_label,
            )
            await session.commit()

        # ── 9. Redis: cache by lead_id for polling + WebSocket ─────────────────
        # "latest" key → GET /suggestions/{lead_id} polling (no message_id needed)
        # message_id key → precise per-message lookup
        await cache.set_suggestions(lead_id, "latest", suggestions)
        await cache.set_suggestions(lead_id, message_id, suggestions)

        # ── 10. NATS: notify WebSocket subscribers ─────────────────────────────
        nats = NATSClient()
        try:
            await nats.connect()
            await nats.publish(
                event_type="betopia.sales.suggestions.ready",
                subject_suffix="conversation.suggestions_ready",
                data={
                    "lead_id": lead_id,
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "intent_label": intent_label,
                    "suggestion_count": len(suggestions),
                },
            )
        except Exception as exc:
            log.warning("p1.nats_notify_failed", error=str(exc))  # non-fatal
        finally:
            try:
                await nats.close()
            except Exception:
                pass

        await cache.close()
        log.info("p1.completed", lead_id=lead_id, suggestions=len(suggestions))

    from src.infrastructure.db.session import engine as _engine  # noqa: PLC0415

    async def _run_and_dispose() -> None:
        try:
            await _run()
        finally:
            # Dispose the connection pool before asyncio.run() closes the event
            # loop. Without this, stale asyncpg connections from the closed loop
            # cause 'NoneType has no attribute send' on the next task invocation.
            await _engine.dispose()

    try:
        asyncio.run(_run_and_dispose())
    except Exception as exc:
        log.error("p1.worker_failed", error=str(exc), lead_id=lead_id)
        raise self.retry(exc=exc, countdown=60)
