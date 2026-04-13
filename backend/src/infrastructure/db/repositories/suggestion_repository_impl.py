# [OWNER: Dev 1 — Data Foundation (P3)]
"""Repository for Suggestion — wraps SuggestionModel with async SQLAlchemy.

Used by:
  - p1_suggestion_worker.py  → bulk_create() after generating 5 suggestions
  - suggestions.py endpoints  → get_by_lead_id() for select/skip feedback
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models.suggestion_model import SuggestionModel


class SuggestionRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_create(
        self,
        suggestions: list[dict],
        message_id: uuid.UUID,
        conversation_id: uuid.UUID,
        lead_id: uuid.UUID,
        intent_label: str | None = None,
    ) -> list[SuggestionModel]:
        """Map LLM output dicts → SuggestionModel rows and bulk insert.

        ``suggestions`` are the raw dicts produced by LLMClient.generate_suggestions():
        each has at minimum: rank, strategy, tone, preview_text, full_text,
        conversion_signal, generated_by.
        """
        now = datetime.now(timezone.utc)
        models: list[SuggestionModel] = []

        for sug in suggestions:
            model = SuggestionModel(
                id=str(uuid.uuid4()),
                conversation_id=str(conversation_id),
                message_id=str(message_id),
                lead_id=str(lead_id),
                rank=int(sug.get("rank", 1)),
                strategy=sug.get("strategy", "discovery"),
                tone=sug.get("tone", "professional"),
                preview_text=sug.get("preview_text", ""),
                full_text=sug.get("full_text", ""),
                conversion_signal=float(sug.get("conversion_signal", 0.5)),
                generated_by=sug.get("generated_by", "gpt-4.1"),
                intent_label=intent_label,
                created_at=now,
                updated_at=now,
            )
            models.append(model)

        self._session.add_all(models)
        await self._session.flush()
        return models

    async def get_by_id(self, suggestion_id: uuid.UUID) -> SuggestionModel | None:
        """Fetch a single suggestion by its PK."""
        result = await self._session.execute(
            select(SuggestionModel).where(SuggestionModel.id == str(suggestion_id))
        )
        return result.scalar_one_or_none()

    async def get_by_lead_id(
        self, lead_id: uuid.UUID, limit: int = 5
    ) -> list[SuggestionModel]:
        """Fetch latest N suggestions for a lead, most recent first."""
        result = await self._session.execute(
            select(SuggestionModel)
            .where(SuggestionModel.lead_id == str(lead_id))
            .order_by(desc(SuggestionModel.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_message_id(self, message_id: uuid.UUID) -> list[SuggestionModel]:
        """Fetch all suggestions for a specific inbound message (usually 5)."""
        result = await self._session.execute(
            select(SuggestionModel)
            .where(SuggestionModel.message_id == str(message_id))
            .order_by(SuggestionModel.rank)
        )
        return list(result.scalars().all())
