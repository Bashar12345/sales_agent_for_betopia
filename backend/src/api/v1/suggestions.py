# [OWNER: Dev 2 — P1 Conversation Engine]
"""P1 Suggestion endpoints — retrieve and provide feedback on suggestions.

GET  /api/v1/suggestions/{lead_id}       — Poll for latest suggestions
GET  /api/v1/suggestions/message/{msg_id} — Suggestions for a specific message
POST /api/v1/suggestions/{id}/select     — Record which suggestion was selected
POST /api/v1/suggestions/{id}/skip       — Record that none were selected (typed manually)
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import Role, get_current_agent, require_roles
from src.domain.entities.suggestion import Suggestion, SuggestionEvent
from src.infrastructure.clients.nats_client import NATSClient
from src.infrastructure.clients.redis_cache_client import RedisCacheClient
from src.infrastructure.db.repositories.suggestion_repository_impl import (
    SuggestionRepositoryImpl,
)
from src.infrastructure.db.session import get_db

router = APIRouter(prefix="/suggestions", tags=["p1-suggestions"])


class SuggestionResponseDTO(BaseModel):
    id: str
    rank: int
    strategy: str
    tone: str
    preview_text: str
    full_text: str
    conversion_signal: float
    generated_by: str
    intent_label: str | None = None


class SuggestionListResponseDTO(BaseModel):
    lead_id: str
    message_id: str | None = None
    suggestions: list[SuggestionResponseDTO]
    intent_label: str | None = None
    # None while pipeline is still running
    ready: bool = True


class SelectSuggestionDTO(BaseModel):
    agent_id: uuid.UUID


# ── Get suggestions for a lead (poll after POST /input/message) ───────────────
@router.get(
    "/{lead_id}",
    response_model=SuggestionListResponseDTO,
    summary="Poll for latest P1 suggestions for a lead",
    dependencies=[Depends(require_roles(
        Role.SALESPERSON, Role.SALES_MANAGER, Role.ADMIN
    ))],
)
async def get_suggestions(
    lead_id: uuid.UUID,
    message_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> SuggestionListResponseDTO:
    """Return the latest generated suggestions for a lead.

    Fast path: reads from Redis cache set by p1_suggestion_worker.
    If message_id is provided, attempts a precise per-message lookup first,
    then falls back to the "latest" key for this lead.
    Returns ready=False while the pipeline is still running.

    TODO (awaits Dev 1): Once SuggestionRepositoryImpl exists, also persist
    selections from the select/skip endpoints and provide DB-backed history.
    """
    cache = RedisCacheClient()
    try:
        cached: list | None = None

        # Try precise message-scoped lookup first
        if message_id is not None:
            cached = await cache.get_suggestions(str(lead_id), str(message_id))

        # Fall back to latest suggestions for this lead
        if cached is None:
            cached = await cache.get_suggestions(str(lead_id), "latest")
    except Exception:
        cached = None
    finally:
        await cache.close()

    if cached:
        return SuggestionListResponseDTO(
            lead_id=str(lead_id),
            message_id=str(message_id) if message_id else None,
            suggestions=cached,
            ready=True,
        )

    # Pipeline still running (or not yet triggered)
    return SuggestionListResponseDTO(
        lead_id=str(lead_id),
        message_id=str(message_id) if message_id else None,
        suggestions=[],
        ready=False,
    )


# ── Record suggestion selection ───────────────────────────────────────────────
@router.post(
    "/{suggestion_id}/select",
    status_code=status.HTTP_200_OK,
    summary="Record that the salesperson selected this suggestion",
    dependencies=[Depends(require_roles(Role.SALESPERSON, Role.SALES_MANAGER, Role.ADMIN))],
)
async def select_suggestion(
    suggestion_id: uuid.UUID,
    dto: SelectSuggestionDTO,
    db: AsyncSession = Depends(get_db),
    agent: dict = Depends(get_current_agent),
) -> dict:
    """Record selection feedback and publish to NATS for A/B analytics."""
    repo = SuggestionRepositoryImpl(db)
    suggestion = await repo.get_by_id(suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found")

    nats_client = NATSClient()
    try:
        await nats_client.connect()
        await nats_client.publish(
            event_type="betopia.sales.conversation.suggestion_selected",
            subject_suffix="conversation.suggestion_selected",
            data={
                "suggestion_id": str(suggestion_id),
                "conversation_id": suggestion.conversation_id,
                "agent_id": agent["sub"],
                "rank": suggestion.rank,
            },
        )
    except Exception:
        pass  # Selection feedback is best-effort — never fail the salesperson
    finally:
        try:
            await nats_client.close()
        except Exception:
            pass

    return {"selected": True, "suggestion_id": str(suggestion_id)}


# ── Record manual typing (no suggestion selected) ─────────────────────────────
@router.post(
    "/skip/{conversation_id}",
    status_code=status.HTTP_200_OK,
    summary="Record that the salesperson typed manually (no suggestion selected)",
    dependencies=[Depends(require_roles(Role.SALESPERSON, Role.SALES_MANAGER, Role.ADMIN))],
)
async def skip_suggestions(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    agent: dict = Depends(get_current_agent),
) -> dict:
    """Record that the salesperson typed manually instead of selecting a suggestion."""
    nats_client = NATSClient()
    try:
        await nats_client.connect()
        await nats_client.publish(
            event_type="betopia.sales.conversation.suggestion_skipped",
            subject_suffix="conversation.suggestion_skipped",
            data={
                "conversation_id": str(conversation_id),
                "agent_id": agent["sub"],
                "manually_typed": True,
            },
        )
    except Exception:
        pass  # Best-effort analytics — never block the salesperson
    finally:
        try:
            await nats_client.close()
        except Exception:
            pass

    return {"skipped": True, "conversation_id": str(conversation_id)}
