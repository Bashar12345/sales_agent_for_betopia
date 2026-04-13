# [OWNER: Dev 1 — Data Foundation (P3)]
"""MySQL implementation of IConversationRepository."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.conversation import Conversation, ConversationStatus
from src.domain.entities.message import Message, MessageDirection, MessageRole
from src.domain.repositories.conversation_repository import IConversationRepository
from src.infrastructure.db.models.conversation_model import ConversationModel, MessageModel


def _msg_to_entity(m: MessageModel) -> Message:
    return Message(
        id=uuid.UUID(m.id),
        conversation_id=uuid.UUID(m.conversation_id),
        role=MessageRole(m.role),
        direction=MessageDirection(m.direction) if m.direction else MessageDirection.IN,
        content=m.content,
        used_in_quotation=m.used_in_quotation,
        created_at=datetime.fromisoformat(m.created_at) if isinstance(m.created_at, str) else m.created_at,
        sent_at=m.sent_at,
        intent_label=m.intent_label,
        suggestion_selected_rank=m.suggestion_selected_rank,
    )


def _to_entity(m: ConversationModel) -> Conversation:
    return Conversation(
        id=uuid.UUID(m.id),
        lead_id=uuid.UUID(m.lead_id),
        agent_id=uuid.UUID(m.agent_id),
        status=ConversationStatus(m.status),
        messages=[_msg_to_entity(msg) for msg in (m.messages or [])],
        vector_id=m.vector_id,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


class ConversationRepositoryImpl(IConversationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, conversation: Conversation) -> Conversation:
        model = ConversationModel(
            id=str(conversation.id),
            lead_id=str(conversation.lead_id),
            agent_id=str(conversation.agent_id),
            status=conversation.status.value,
            vector_id=conversation.vector_id,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )
        for msg in conversation.messages:
            model.messages.append(
                MessageModel(
                    id=str(msg.id),
                    conversation_id=str(msg.conversation_id),
                    role=msg.role.value,
                    content=msg.content,
                    used_in_quotation=msg.used_in_quotation,
                    created_at=msg.created_at.isoformat(),
                )
            )
        self._session.add(model)
        await self._session.flush()
        return conversation

    async def get_by_id(self, conversation_id: uuid.UUID) -> Conversation | None:
        result = await self._session.execute(
            select(ConversationModel).where(ConversationModel.id == str(conversation_id))
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def get_by_lead_id(self, lead_id: uuid.UUID) -> list[Conversation]:
        result = await self._session.execute(
            select(ConversationModel).where(ConversationModel.lead_id == str(lead_id))
        )
        return [_to_entity(m) for m in result.scalars().all()]

    async def update(self, conversation: Conversation) -> Conversation:
        result = await self._session.execute(
            select(ConversationModel).where(ConversationModel.id == str(conversation.id))
        )
        model = result.scalar_one_or_none()
        if not model:
            return await self.create(conversation)

        model.status = conversation.status.value
        model.vector_id = conversation.vector_id
        model.updated_at = datetime.now(timezone.utc)

        # Sync messages: add new ones only
        existing_ids = {m.id for m in model.messages}
        for msg in conversation.messages:
            if str(msg.id) not in existing_ids:
                model.messages.append(
                    MessageModel(
                        id=str(msg.id),
                        conversation_id=str(msg.conversation_id),
                        role=msg.role.value,
                        content=msg.content,
                        used_in_quotation=msg.used_in_quotation,
                        created_at=msg.created_at.isoformat(),
                    )
                )
        await self._session.flush()
        return conversation

    async def delete(self, conversation_id: uuid.UUID) -> None:
        result = await self._session.execute(
            select(ConversationModel).where(ConversationModel.id == str(conversation_id))
        )
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()

    async def add_message(self, message: Message) -> Message:
        """Persist a single new message to an existing conversation.

        Called by POST /input/message after the Message entity is created.
        The conversation must already exist (no cascade create here).
        """
        model = MessageModel(
            id=str(message.id),
            conversation_id=str(message.conversation_id),
            role=message.role.value,
            direction=message.direction.value if message.direction else None,
            content=message.content,
            used_in_quotation=message.used_in_quotation,
            created_at=message.created_at.isoformat(),
            sent_at=message.sent_at,
            intent_label=message.intent_label,
            suggestion_selected_rank=message.suggestion_selected_rank,
        )
        self._session.add(model)
        await self._session.flush()
        return message
