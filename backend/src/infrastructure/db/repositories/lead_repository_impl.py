# [OWNER: Zohra — Data Foundation (P3)]
"""MySQL implementation of ILeadRepository using SQLAlchemy async."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AlreadyExistsError
from src.domain.entities.lead import Lead, LeadSource, LeadStatus
from src.domain.repositories.lead_repository import ILeadRepository
from src.infrastructure.db.models.lead_model import LeadModel


def _to_entity(m: LeadModel) -> Lead:
    return Lead(
        id=uuid.UUID(m.id),
        fiverr_order_id=m.fiverr_order_id,
        fiverr_buyer_username=m.fiverr_buyer_username,
        name=m.name,
        email=m.email,
        budget=m.budget,
        requirement_summary=m.requirement_summary,
        status=LeadStatus(m.status),
        source=LeadSource(m.source),
        assigned_agent_id=uuid.UUID(m.assigned_agent_id) if m.assigned_agent_id else None,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _to_model(e: Lead) -> LeadModel:
    return LeadModel(
        id=str(e.id),
        fiverr_order_id=e.fiverr_order_id,
        fiverr_buyer_username=e.fiverr_buyer_username,
        name=e.name,
        email=e.email,
        budget=e.budget,
        requirement_summary=e.requirement_summary,
        status=e.status.value,
        source=e.source.value,
        assigned_agent_id=str(e.assigned_agent_id) if e.assigned_agent_id else None,
        created_at=e.created_at,
        updated_at=e.updated_at,
    )


class LeadRepositoryImpl(ILeadRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, lead: Lead) -> Lead:
        if lead.fiverr_order_id:
            existing = await self.get_by_fiverr_order_id(lead.fiverr_order_id)
            if existing:
                raise AlreadyExistsError(f"Lead with Fiverr order {lead.fiverr_order_id} exists")
        model = _to_model(lead)
        self._session.add(model)
        await self._session.flush()
        return lead

    async def get_by_id(self, lead_id: uuid.UUID) -> Lead | None:
        result = await self._session.execute(
            select(LeadModel).where(LeadModel.id == str(lead_id))
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def get_by_fiverr_order_id(self, order_id: str) -> Lead | None:
        result = await self._session.execute(
            select(LeadModel).where(LeadModel.fiverr_order_id == order_id)
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def list_all(self, limit: int = 50, offset: int = 0) -> list[Lead]:
        result = await self._session.execute(
            select(LeadModel).order_by(LeadModel.created_at.desc()).limit(limit).offset(offset)
        )
        return [_to_entity(m) for m in result.scalars().all()]

    async def list_by_status(self, status: LeadStatus) -> list[Lead]:
        result = await self._session.execute(
            select(LeadModel).where(LeadModel.status == status.value)
        )
        return [_to_entity(m) for m in result.scalars().all()]

    async def update(self, lead: Lead) -> Lead:
        result = await self._session.execute(
            select(LeadModel).where(LeadModel.id == str(lead.id))
        )
        model = result.scalar_one_or_none()
        if not model:
            model = _to_model(lead)
            self._session.add(model)
        else:
            model.name = lead.name
            model.email = lead.email
            model.budget = lead.budget
            model.requirement_summary = lead.requirement_summary
            model.status = lead.status.value
            model.assigned_agent_id = str(lead.assigned_agent_id) if lead.assigned_agent_id else None
            model.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return lead

    async def delete(self, lead_id: uuid.UUID) -> None:
        result = await self._session.execute(
            select(LeadModel).where(LeadModel.id == str(lead_id))
        )
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()
