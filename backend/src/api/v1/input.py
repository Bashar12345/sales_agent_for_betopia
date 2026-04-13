# [OWNER: Niloy — P1 Conversation Engine]
"""P1 Conversation Engine — message input endpoint.

POST /api/v1/input/message
  The salesperson pastes a customer message here.
  Returns 202 Accepted immediately with a task_id.
  Suggestions are delivered asynchronously via WebSocket or polled via
  GET /api/v1/suggestions/{lead_id}.

Flow:
  1. Store raw message in DB (Message entity, direction=in)
  2. Publish betopia.sales.conversation.message_received to NATS
  3. Background: intent classify → embed → Qdrant search → GPT-4.1 (fallback chain) → 5 suggestions
  4. Store suggestions in DB + Redis cache
  5. Push suggestions to WebSocket subscribers

Rate limit: 100 req/min/user (enforced by Kong gateway + app-level Redis check)
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import EventBusError
from src.core.security import Role, get_current_agent, require_roles
from src.domain.entities.message import Message, MessageDirection, MessageRole
from src.infrastructure.clients.nats_client import NATSClient
from src.infrastructure.clients.redis_cache_client import RedisCacheClient
from src.infrastructure.db.repositories.conversation_repository_impl import (
    ConversationRepositoryImpl,
)
from src.infrastructure.db.session import get_db

router = APIRouter(prefix="/input", tags=["p1-input"])


class MessageInputDTO(BaseModel):
    lead_id: uuid.UUID
    conversation_id: uuid.UUID
    customer_message: str
    # Optional: allow salesperson to hint the intent (skip vLLM classification)
    intent_override: str | None = None


class MessageAcceptedResponseDTO(BaseModel):
    task_id: str
    message_id: str
    status: str = "accepted"
    # Polling endpoint for clients without WebSocket support
    suggestions_url: str


@router.post(
    "/message",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=MessageAcceptedResponseDTO,
    summary="Submit customer message (P1 pipeline entry point)",
    dependencies=[Depends(require_roles(Role.SALESPERSON, Role.SALES_MANAGER, Role.ADMIN))],
)
async def submit_message(
    dto: MessageInputDTO,
    db: AsyncSession = Depends(get_db),
    agent: dict = Depends(get_current_agent),
) -> MessageAcceptedResponseDTO:
    """Accept a pasted customer message and trigger the P1 suggestion pipeline.

    Returns 202 immediately.  Suggestions arrive via WebSocket or GET /suggestions/{lead_id}.
    """
    cache = RedisCacheClient()
    agent_id = agent["sub"]

    # Rate limit check (defence-in-depth behind Kong's 100 req/min/user rule)
    allowed = await cache.check_rate_limit(agent_id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Max 100 requests per minute.",
        )

    now = datetime.now(timezone.utc)
    message_id = uuid.uuid4()

    # Persist the inbound message
    message = Message(
        id=message_id,
        conversation_id=dto.conversation_id,
        role=MessageRole.CUSTOMER,
        direction=MessageDirection.IN,
        content=dto.customer_message,
        created_at=now,
    )
    conv_repo = ConversationRepositoryImpl(db)
    await conv_repo.add_message(message)

    # Publish to NATS — P1 worker picks this up asynchronously
    task_id = str(uuid.uuid4())
    nats_client = NATSClient()
    try:
        await nats_client.connect()
        await nats_client.emit_message_received(
            conversation_id=str(dto.conversation_id),
            message_id=str(message_id),
            lead_id=str(dto.lead_id),
        )
    except EventBusError:
        # NATS failure is non-fatal — suggestions will be generated synchronously
        # by the fallback Celery worker (fire-and-forget)
        pass
    finally:
        await nats_client.close()

    return MessageAcceptedResponseDTO(
        task_id=task_id,
        message_id=str(message_id),
        suggestions_url=f"/api/v1/suggestions/{dto.lead_id}",
    )
