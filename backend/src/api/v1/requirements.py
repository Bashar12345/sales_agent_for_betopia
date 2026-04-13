# [OWNER: Akash — P2 Requirements Agent]
"""P2 Requirements Agent — document ingestion and structured extraction.

POST /api/v1/requirements/upload        — Upload document (PDF/DOCX/PPTX/Excel/image/audio)
GET  /api/v1/requirements/{id}          — Get extraction status + result
POST /api/v1/requirements/{id}/approve  — SALES_MANAGER approves for proposal generation
GET  /api/v1/requirements/lead/{lead_id} — All requirements docs for a lead

Supported MIME types (from v1_extraction_prompt.yaml):
  application/pdf
  application/vnd.openxmlformats-officedocument.wordprocessingml.document
  application/vnd.openxmlformats-officedocument.presentationml.presentation
  application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
  image/png, image/jpeg  (GPT-4.1 Vision)
  audio/mpeg             (OpenAI Whisper)
  text/plain
"""

import uuid
from datetime import datetime, timezone
from typing import Annotated

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import RequirementsExtractionError
from src.core.security import Role, require_roles
from src.core.settings import settings
from src.domain.entities.requirements_doc import ExtractionStatus, RequirementsDoc
from src.infrastructure.clients.nats_client import NATSClient
from src.infrastructure.db.session import get_db

router = APIRouter(prefix="/requirements", tags=["p2-requirements"])

_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/png",
    "image/jpeg",
    "audio/mpeg",
    "text/plain",
}


# ── Upload document ───────────────────────────────────────────────────────────
@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RequirementsDoc,
    summary="Upload requirements document for P2 extraction",
    dependencies=[Depends(require_roles(Role.SALESPERSON, Role.SALES_MANAGER, Role.ADMIN))],
)
async def upload_requirements(
    lead_id: Annotated[uuid.UUID, Form()],
    conversation_id: Annotated[uuid.UUID | None, Form()] = None,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> RequirementsDoc:
    """Upload a document to the P2 Requirements Agent for extraction.

    Returns 202 with a RequirementsDoc record in PENDING status.
    Extraction runs asynchronously; poll GET /requirements/{id} for status.
    """
    if file.content_type not in _ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {file.content_type}. "
                   f"Allowed: {', '.join(sorted(_ALLOWED_MIME_TYPES))}",
        )

    # Save file to disk
    file_id = uuid.uuid4()
    safe_name = f"{file_id}_{file.filename or 'upload'}"
    save_path = f"{settings.DOC_OUTPUT_DIR}/{safe_name}"
    async with aiofiles.open(save_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    now = datetime.now(timezone.utc)
    doc = RequirementsDoc(
        id=file_id,
        lead_id=lead_id,
        conversation_id=conversation_id,
        source_filename=file.filename,
        source_mime_type=file.content_type,
        status=ExtractionStatus.PENDING,
        created_at=now,
        updated_at=now,
    )

    # TODO: persist to DB via RequirementsDocRepositoryImpl
    # TODO: enqueue Celery task: extract_requirements.delay(str(doc.id), save_path)

    # Notify NATS (P3 observability)
    nats_client = NATSClient()
    try:
        await nats_client.connect()
        await nats_client.publish(
            event_type="betopia.sales.requirements.upload_received",
            subject_suffix="requirements.upload_received",
            data={"doc_id": str(doc.id), "lead_id": str(lead_id), "mime": file.content_type},
        )
    except Exception:
        pass
    finally:
        await nats_client.close()

    return doc


# ── Get extraction result ─────────────────────────────────────────────────────
@router.get(
    "/{doc_id}",
    response_model=RequirementsDoc,
    summary="Get P2 extraction status and structured results",
    dependencies=[Depends(require_roles(
        Role.SALESPERSON, Role.SALES_MANAGER, Role.ADMIN, Role.READ_ONLY
    ))],
)
async def get_requirements(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RequirementsDoc:
    # TODO: implement RequirementsDocRepositoryImpl.get_by_id
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


# ── SALES_MANAGER approves for proposal generation ───────────────────────────
@router.post(
    "/{doc_id}/approve",
    status_code=status.HTTP_200_OK,
    summary="Approve requirements doc — triggers proposal PDF generation",
    dependencies=[Depends(require_roles(Role.SALES_MANAGER, Role.ADMIN))],
)
async def approve_requirements(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    # TODO: fetch doc, set status=APPROVED, emit NATS event → triggers P2 proposal gen
    return {"approved": True, "doc_id": str(doc_id)}


# ── All requirements docs for a lead ─────────────────────────────────────────
@router.get(
    "/lead/{lead_id}",
    response_model=list[RequirementsDoc],
    summary="List all requirements documents for a lead",
    dependencies=[Depends(require_roles(
        Role.SALESPERSON, Role.SALES_MANAGER, Role.ADMIN, Role.READ_ONLY
    ))],
)
async def list_requirements(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[RequirementsDoc]:
    # TODO: implement RequirementsDocRepositoryImpl.list_by_lead
    return []
