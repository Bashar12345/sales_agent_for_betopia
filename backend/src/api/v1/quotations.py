# [OWNER: Akash — P2 Requirements Agent]
"""Quotation endpoints — generate, view, update, export to .docx."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dto.quotation_dto import ExportQuotationDTO, GenerateQuotationDTO, UpdateQuotationDTO
from src.application.use_cases.generate_quotation import GenerateQuotationUseCase
from src.core.exceptions import LLMError, NotFoundError, ValidationError
from src.domain.entities.quotation import Quotation
from src.domain.services.quotation_service import QuotationService
from src.infrastructure.clients.chromadb_client import ChromaDBClient
from src.infrastructure.clients.document_generator import DocumentGenerator
from src.infrastructure.clients.llm_client import LLMClient
from src.infrastructure.db.repositories.conversation_repository_impl import ConversationRepositoryImpl
from src.infrastructure.db.repositories.lead_repository_impl import LeadRepositoryImpl
from src.infrastructure.db.repositories.quotation_repository_impl import QuotationRepositoryImpl
from src.infrastructure.db.session import get_db

router = APIRouter(prefix="/quotations", tags=["quotations"])


def _deps(db: AsyncSession = Depends(get_db)):
    return {
        "conv_repo": ConversationRepositoryImpl(db),
        "lead_repo": LeadRepositoryImpl(db),
        "quot_repo": QuotationRepositoryImpl(db),
        "llm": LLMClient(),
        "vs": ChromaDBClient(),
        "svc": QuotationService(),
    }


@router.post("/generate", status_code=status.HTTP_201_CREATED, response_model=Quotation)
async def generate_quotation(
    dto: GenerateQuotationDTO,
    db: AsyncSession = Depends(get_db),
) -> Quotation:
    deps = _deps(db)
    use_case = GenerateQuotationUseCase(**deps)
    try:
        return await use_case.execute(dto)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (LLMError, ValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("/{quotation_id}", response_model=Quotation)
async def get_quotation(
    quotation_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Quotation:
    repo = QuotationRepositoryImpl(db)
    quot = await repo.get_by_id(quotation_id)
    if not quot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")
    return quot


@router.get("/conversation/{conversation_id}", response_model=list[Quotation])
async def quotations_for_conversation(
    conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[Quotation]:
    return await QuotationRepositoryImpl(db).get_by_conversation_id(conversation_id)


@router.patch("/{quotation_id}", response_model=Quotation)
async def update_quotation(
    quotation_id: uuid.UUID,
    dto: UpdateQuotationDTO,
    db: AsyncSession = Depends(get_db),
) -> Quotation:
    repo = QuotationRepositoryImpl(db)
    quot = await repo.get_by_id(quotation_id)
    if not quot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")
    if dto.title is not None:
        quot.title = dto.title
    if dto.line_items is not None:
        svc = QuotationService()
        errors = svc.validate_line_items(dto.line_items)
        if errors:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)
        quot = svc.apply_line_items(quot, dto.line_items)
    if dto.notes is not None:
        quot.notes = dto.notes
    if dto.currency is not None:
        quot.currency = dto.currency
    return await repo.update(quot)


@router.post("/{quotation_id}/export")
async def export_quotation_doc(
    quotation_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate the .docx file. Returns the download path."""
    repo = QuotationRepositoryImpl(db)
    quot = await repo.get_by_id(quotation_id)
    if not quot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")

    generator = DocumentGenerator()
    doc_path = await generator.generate_quotation_doc(
        quotation=quot, lead_name="Customer", agent_name="Agent"
    )
    quot.doc_path = doc_path
    await repo.update(quot)
    return {"quotation_id": str(quotation_id), "doc_path": doc_path}


@router.get("/{quotation_id}/download")
async def download_quotation(
    quotation_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> FileResponse:
    repo = QuotationRepositoryImpl(db)
    quot = await repo.get_by_id(quotation_id)
    if not quot or not quot.doc_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not generated yet. Call /export first.",
        )
    return FileResponse(
        path=quot.doc_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"quotation_{quotation_id}.docx",
    )
