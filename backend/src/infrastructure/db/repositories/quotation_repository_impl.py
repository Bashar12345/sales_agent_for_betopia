# [OWNER: Dev 1 — Data Foundation (P3)]
"""MySQL implementation of IQuotationRepository."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.quotation import LineItem, Quotation, QuotationStatus
from src.domain.repositories.quotation_repository import IQuotationRepository
from src.infrastructure.db.models.quotation_model import QuotationModel


def _to_entity(m: QuotationModel) -> Quotation:
    return Quotation(
        id=uuid.UUID(m.id),
        conversation_id=uuid.UUID(m.conversation_id),
        lead_id=uuid.UUID(m.lead_id),
        agent_id=uuid.UUID(m.agent_id),
        title=m.title,
        line_items=[LineItem(**item) for item in (m.line_items or [])],
        notes=m.notes or "",
        total_amount=m.total_amount,
        currency=m.currency,
        status=QuotationStatus(m.status),
        doc_path=m.doc_path,
        vector_id=m.vector_id,
        odoo_order_id=m.odoo_order_id,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


class QuotationRepositoryImpl(IQuotationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, quotation: Quotation) -> Quotation:
        model = QuotationModel(
            id=str(quotation.id),
            conversation_id=str(quotation.conversation_id),
            lead_id=str(quotation.lead_id),
            agent_id=str(quotation.agent_id),
            title=quotation.title,
            line_items=[item.model_dump() for item in quotation.line_items],
            notes=quotation.notes,
            total_amount=quotation.total_amount,
            currency=quotation.currency,
            status=quotation.status.value,
            doc_path=quotation.doc_path,
            vector_id=quotation.vector_id,
            odoo_order_id=quotation.odoo_order_id,
            created_at=quotation.created_at,
            updated_at=quotation.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        return quotation

    async def get_by_id(self, quotation_id: uuid.UUID) -> Quotation | None:
        result = await self._session.execute(
            select(QuotationModel).where(QuotationModel.id == str(quotation_id))
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def get_by_conversation_id(self, conversation_id: uuid.UUID) -> list[Quotation]:
        result = await self._session.execute(
            select(QuotationModel).where(QuotationModel.conversation_id == str(conversation_id))
        )
        return [_to_entity(m) for m in result.scalars().all()]

    async def get_by_lead_id(self, lead_id: uuid.UUID) -> list[Quotation]:
        result = await self._session.execute(
            select(QuotationModel).where(QuotationModel.lead_id == str(lead_id))
        )
        return [_to_entity(m) for m in result.scalars().all()]

    async def update(self, quotation: Quotation) -> Quotation:
        result = await self._session.execute(
            select(QuotationModel).where(QuotationModel.id == str(quotation.id))
        )
        model = result.scalar_one_or_none()
        if not model:
            return await self.create(quotation)

        model.title = quotation.title
        model.line_items = [item.model_dump() for item in quotation.line_items]
        model.notes = quotation.notes
        model.total_amount = quotation.total_amount
        model.currency = quotation.currency
        model.status = quotation.status.value
        model.doc_path = quotation.doc_path
        model.vector_id = quotation.vector_id
        model.odoo_order_id = quotation.odoo_order_id
        model.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return quotation
