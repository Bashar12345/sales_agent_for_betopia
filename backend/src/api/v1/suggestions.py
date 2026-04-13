# [OWNER: Niloy — P1 Conversation Engine]
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

    If message_id is provided, returns suggestions specific to that message.
    Returns ready=False with an empty list while the pipeline is still running.
    """
    # TODO: implement SuggestionRepositoryImpl and query
    # For now returns a placeholder so the endpoint is discoverable
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
    # TODO: fetch suggestion from DB, create SuggestionEvent, emit to NATS
    nats_client = NATSClient()
    try:
        await nats_client.connect()
        await nats_client.emit_suggestion_selected(
            suggestion_id=str(suggestion_id),
            conversation_id="",   # TODO: fetch from suggestion record
            agent_id=agent["sub"],
            rank=1,               # TODO: fetch from suggestion record
        )
    except Exception:
        pass  # Selection feedback is best-effort
    finally:
        await nats_client.close()

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
    # TODO: create SuggestionEvent(manually_typed=True)
    return {"skipped": True, "conversation_id": str(conversation_id)}
