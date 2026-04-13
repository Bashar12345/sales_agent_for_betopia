# [OWNER: Niloy — P1 Conversation Engine]
"""Conversation endpoints — create, add messages, retrieve transcripts."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dto.conversation_dto import AddMessageDTO, CreateConversationDTO
from src.domain.entities.conversation import Conversation, ConversationStatus
from src.domain.entities.message import Message
from src.infrastructure.db.repositories.conversation_repository_impl import (
    ConversationRepositoryImpl,
)
from src.infrastructure.db.session import get_db

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _repo(db: AsyncSession = Depends(get_db)) -> ConversationRepositoryImpl:
    return ConversationRepositoryImpl(db)


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=Conversation)
async def create_conversation(
    dto: CreateConversationDTO, db: AsyncSession = Depends(get_db)
) -> Conversation:
    now = datetime.now(timezone.utc)
    conv = Conversation(
        id=uuid.uuid4(),
        lead_id=dto.lead_id,
        agent_id=dto.agent_id,
        status=ConversationStatus.ACTIVE,
        messages=[],
        created_at=now,
        updated_at=now,
    )
    return await _repo(db).create(conv)


@router.get("/{conversation_id}", response_model=Conversation)
async def get_conversation(
    conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Conversation:
    conv = await _repo(db).get_by_id(conversation_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv


@router.get("/lead/{lead_id}", response_model=list[Conversation])
async def conversations_for_lead(
    lead_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[Conversation]:
    return await _repo(db).get_by_lead_id(lead_id)


@router.post("/{conversation_id}/messages", response_model=Conversation)
async def add_message(
    conversation_id: uuid.UUID,
    dto: AddMessageDTO,
    db: AsyncSession = Depends(get_db),
) -> Conversation:
    repo = _repo(db)
    conv = await repo.get_by_id(conversation_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role=dto.role,
        content=dto.content,
        created_at=datetime.now(timezone.utc),
    )
    conv.messages.append(msg)
    conv.updated_at = datetime.now(timezone.utc)
    return await repo.update(conv)


@router.get("/{conversation_id}/transcript")
async def get_transcript(
    conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> dict:
    conv = await _repo(db).get_by_id(conversation_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return {"conversation_id": str(conversation_id), "transcript": conv.get_transcript()}
