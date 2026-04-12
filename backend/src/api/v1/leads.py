"""Lead endpoints — CRUD only.

v3.0 NOTE: The Fiverr webhook endpoint (POST /leads/webhook/fiverr) has been
REMOVED per security mandate.  There is zero Fiverr API connection.
Leads are created manually by the salesperson via POST /leads/.

The salesperson registers a lead when they see a new Fiverr message, entering
the buyer's name and initial message.  The P1 pipeline is then triggered by
POST /api/v1/input/message.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dto.lead_dto import CreateLeadDTO, UpdateLeadStatusDTO
from src.core.exceptions import AlreadyExistsError, NotFoundError
from src.core.security import Role, require_roles
from src.domain.entities.lead import Lead, LeadStatus
from src.infrastructure.db.repositories.lead_repository_impl import LeadRepositoryImpl
from src.infrastructure.db.session import get_db

router = APIRouter(prefix="/leads", tags=["leads"])


def _lead_repo(db: AsyncSession = Depends(get_db)) -> LeadRepositoryImpl:
    return LeadRepositoryImpl(db)


# ── Create Lead (manual — salesperson registers a Fiverr buyer) ───────────────
@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=Lead,
    dependencies=[Depends(require_roles(Role.SALESPERSON, Role.SALES_MANAGER, Role.ADMIN))],
)
async def create_lead(
    dto: CreateLeadDTO,
    db: AsyncSession = Depends(get_db),
) -> Lead:
    repo = _lead_repo(db)
    now = datetime.now(timezone.utc)
    lead = Lead(
        id=uuid.uuid4(),
        **dto.model_dump(),
        status=LeadStatus.NEW,
        created_at=now,
        updated_at=now,
    )
    try:
        return await repo.create(lead)
    except AlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


# ── List Leads ────────────────────────────────────────────────────────────────
@router.get(
    "/",
    response_model=list[Lead],
    dependencies=[Depends(require_roles(
        Role.SALESPERSON, Role.SALES_MANAGER, Role.ADMIN, Role.READ_ONLY
    ))],
)
async def list_leads(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[Lead]:
    return await _lead_repo(db).list_all(limit=limit, offset=offset)


# ── Get Lead ──────────────────────────────────────────────────────────────────
@router.get(
    "/{lead_id}",
    response_model=Lead,
    dependencies=[Depends(require_roles(
        Role.SALESPERSON, Role.SALES_MANAGER, Role.ADMIN, Role.READ_ONLY
    ))],
)
async def get_lead(lead_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Lead:
    lead = await _lead_repo(db).get_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


# ── Update Lead Status ────────────────────────────────────────────────────────
@router.patch(
    "/{lead_id}/status",
    response_model=Lead,
    dependencies=[Depends(require_roles(Role.SALESPERSON, Role.SALES_MANAGER, Role.ADMIN))],
)
async def update_lead_status(
    lead_id: uuid.UUID,
    dto: UpdateLeadStatusDTO,
    db: AsyncSession = Depends(get_db),
) -> Lead:
    repo = _lead_repo(db)
    lead = await repo.get_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    lead.status = dto.status
    lead.updated_at = datetime.now(timezone.utc)
    return await repo.update(lead)


# ── Delete Lead (admin only) ──────────────────────────────────────────────────
@router.delete(
    "/{lead_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(Role.ADMIN))],
)
async def delete_lead(lead_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    repo = _lead_repo(db)
    lead = await repo.get_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    await repo.delete(lead_id)
