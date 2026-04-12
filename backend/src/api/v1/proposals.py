"""P2 Proposals — PDF generation and delivery.

POST /api/v1/proposals/generate         — Generate proposal PDF from requirements + quotation
GET  /api/v1/proposals/{id}             — Get proposal status
GET  /api/v1/proposals/{id}/download    — Download PDF (short-lived signed URL / stream)
POST /api/v1/proposals/{id}/send        — Mark as sent (update status → SENT)
GET  /api/v1/proposals/lead/{lead_id}   — All proposals for a lead

Access control:
  Generate / Send: SALESPERSON, SALES_MANAGER, ADMIN
  Approve PDF before send: SALES_MANAGER, ADMIN
  Read-only view:  READ_ONLY
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import Role, require_roles
from src.core.settings import settings
from src.domain.entities.proposal import Proposal, ProposalStatus
from src.infrastructure.db.session import get_db

router = APIRouter(prefix="/proposals", tags=["p2-proposals"])


class GenerateProposalDTO(BaseModel):
    lead_id: uuid.UUID
    quotation_id: uuid.UUID
    requirements_doc_id: uuid.UUID | None = None
    title: str
    executive_summary: str = ""
    valid_days: int = 30


# ── Generate proposal ─────────────────────────────────────────────────────────
@router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Proposal,
    summary="Trigger P2 proposal PDF generation",
    dependencies=[Depends(require_roles(Role.SALESPERSON, Role.SALES_MANAGER, Role.ADMIN))],
)
async def generate_proposal(
    dto: GenerateProposalDTO,
    db: AsyncSession = Depends(get_db),
) -> Proposal:
    """Queue proposal PDF generation.

    Returns 202 with a Proposal in GENERATING status.
    Poll GET /proposals/{id} until status=READY, then download via /proposals/{id}/download.
    """
    now = datetime.now(timezone.utc)
    proposal = Proposal(
        id=uuid.uuid4(),
        quotation_id=dto.quotation_id,
        requirements_doc_id=dto.requirements_doc_id,
        lead_id=dto.lead_id,
        agent_id=uuid.uuid4(),   # TODO: get from JWT claims
        title=dto.title,
        executive_summary=dto.executive_summary,
        valid_days=dto.valid_days,
        status=ProposalStatus.GENERATING,
        created_at=now,
        updated_at=now,
    )
    # TODO: persist to DB via ProposalRepositoryImpl
    # TODO: enqueue: generate_proposal_pdf.delay(str(proposal.id))
    return proposal


# ── Get proposal status ───────────────────────────────────────────────────────
@router.get(
    "/{proposal_id}",
    response_model=Proposal,
    summary="Get proposal status and metadata",
    dependencies=[Depends(require_roles(
        Role.SALESPERSON, Role.SALES_MANAGER, Role.ADMIN, Role.READ_ONLY
    ))],
)
async def get_proposal(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Proposal:
    # TODO: ProposalRepositoryImpl.get_by_id
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")


# ── Download PDF ──────────────────────────────────────────────────────────────
@router.get(
    "/{proposal_id}/download",
    summary="Download the generated proposal PDF",
    dependencies=[Depends(require_roles(
        Role.SALESPERSON, Role.SALES_MANAGER, Role.ADMIN
    ))],
)
async def download_proposal(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Stream the PDF file from disk.

    In production, replace this with a pre-signed S3/GCS URL redirect.
    """
    # TODO: fetch proposal from DB, verify status=READY
    pdf_path = Path(settings.PROPOSAL_OUTPUT_DIR) / f"{proposal_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal PDF not yet generated or not found",
        )
    return Response(
        content=pdf_path.read_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="proposal_{proposal_id}.pdf"'},
    )


# ── Mark proposal as sent ─────────────────────────────────────────────────────
@router.post(
    "/{proposal_id}/send",
    status_code=status.HTTP_200_OK,
    summary="Mark proposal as sent to the lead",
    dependencies=[Depends(require_roles(Role.SALESPERSON, Role.SALES_MANAGER, Role.ADMIN))],
)
async def mark_proposal_sent(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    # TODO: update proposal status → SENT, emit NATS event
    return {"sent": True, "proposal_id": str(proposal_id)}


# ── List proposals for a lead ─────────────────────────────────────────────────
@router.get(
    "/lead/{lead_id}",
    response_model=list[Proposal],
    summary="List all proposals for a lead",
    dependencies=[Depends(require_roles(
        Role.SALESPERSON, Role.SALES_MANAGER, Role.ADMIN, Role.READ_ONLY
    ))],
)
async def list_proposals(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[Proposal]:
    # TODO: ProposalRepositoryImpl.list_by_lead
    return []
