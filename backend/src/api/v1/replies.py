# [OWNER: Dev 4 — Frontend, Auth & DevOps]
"""Reply-suggestion endpoint — DEPRECATED in v3.0.

POST /api/v1/replies/suggest is kept for backwards-compatibility.

Preferred v3.0 flow:
  1. POST /api/v1/input/message       → 202 + task_id
  2. GET  /api/v1/suggestions/{lead_id} → 5 structured suggestions (poll)
     OR subscribe to WebSocket ws://.../api/v1/ws/suggestions/{lead_id}

This endpoint now delegates to the new P1 pipeline internally.
Returns up to 5 suggestions in the old 3-suggestion response format for
clients that haven't migrated yet.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dto.reply_dto import ReplySuggestionsResponseDTO, SuggestRepliesDTO
from src.application.use_cases.suggest_replies import SuggestRepliesUseCase
from src.core.exceptions import LLMError
from src.core.security import Role, require_roles
from src.domain.services.reply_service import ReplyService
from src.infrastructure.clients.llm_client import LLMClient
from src.infrastructure.clients.qdrant_client import QdrantVectorClient
from src.infrastructure.db.repositories.conversation_repository_impl import (
    ConversationRepositoryImpl,
)
from src.infrastructure.db.session import get_db

router = APIRouter(prefix="/replies", tags=["replies (deprecated)"])


@router.post(
    "/suggest",
    response_model=ReplySuggestionsResponseDTO,
    deprecated=True,
    summary="[DEPRECATED] Use POST /input/message + GET /suggestions/{lead_id} instead",
    dependencies=[Depends(require_roles(Role.SALESPERSON, Role.SALES_MANAGER, Role.ADMIN))],
)
async def suggest_replies(
    dto: SuggestRepliesDTO,
    db: AsyncSession = Depends(get_db),
) -> ReplySuggestionsResponseDTO:
    use_case = SuggestRepliesUseCase(
        conversation_repo=ConversationRepositoryImpl(db),
        llm_port=LLMClient(),
        vector_store=QdrantVectorClient(),
        reply_service=ReplyService(),
    )
    try:
        return await use_case.execute(dto)
    except LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM error: {exc}",
        )
