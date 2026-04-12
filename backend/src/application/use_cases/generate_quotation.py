"""GenerateQuotation — core AI flow: conversation → quotation.

Steps:
  1. Load conversation + messages from MySQL
  2. Query ChromaDB for similar past quotations + relevant resources
  3. Call LLM to generate line items and notes
  4. Apply domain validation rules
  5. Persist quotation to MySQL
  6. Embed quotation text into ChromaDB for future similarity
  7. Dispatch background job to generate .docx file
"""

import uuid
from datetime import datetime, timezone

from src.application.dto.quotation_dto import GenerateQuotationDTO
from src.application.ports.llm_port import ILLMPort
from src.application.ports.vector_store_port import IVectorStorePort
from src.core.exceptions import NotFoundError, ValidationError
from src.core.settings import settings
from src.domain.entities.conversation import ConversationStatus
from src.domain.entities.lead import LeadStatus
from src.domain.entities.quotation import Quotation, QuotationStatus
from src.domain.repositories.conversation_repository import IConversationRepository
from src.domain.repositories.lead_repository import ILeadRepository
from src.domain.repositories.quotation_repository import IQuotationRepository
from src.domain.services.quotation_service import QuotationService


class GenerateQuotationUseCase:
    def __init__(
        self,
        conversation_repo: IConversationRepository,
        lead_repo: ILeadRepository,
        quotation_repo: IQuotationRepository,
        llm_port: ILLMPort,
        vector_store: IVectorStorePort,
        quotation_service: QuotationService,
    ) -> None:
        self._conv_repo = conversation_repo
        self._lead_repo = lead_repo
        self._quot_repo = quotation_repo
        self._llm = llm_port
        self._vs = vector_store
        self._svc = quotation_service

    async def execute(self, dto: GenerateQuotationDTO) -> Quotation:
        conversation = await self._conv_repo.get_by_id(dto.conversation_id)
        if not conversation:
            raise NotFoundError(f"Conversation {dto.conversation_id} not found")

        lead = await self._lead_repo.get_by_id(conversation.lead_id)
        if not lead:
            raise NotFoundError(f"Lead {conversation.lead_id} not found")

        transcript = conversation.get_transcript()

        # Retrieve similar quotations and resources from ChromaDB
        similar_quots = await self._vs.query_similar(
            settings.CHROMA_COLLECTION_QUOTATIONS, transcript, n_results=5
        )
        resources = await self._vs.query_similar(
            settings.CHROMA_COLLECTION_RESOURCES, transcript, n_results=5
        )

        similar_texts = [d["text"] for d in similar_quots]
        resource_texts = [d["text"] for d in resources]

        # LLM generates structured line items
        line_items, notes = await self._llm.generate_quotation_items(
            transcript=transcript,
            similar_quotations=similar_texts,
            resources_context=resource_texts,
        )

        # Domain validation
        errors = self._svc.validate_line_items(line_items)
        if errors:
            raise ValidationError("; ".join(errors))

        now = datetime.now(timezone.utc)
        quotation = Quotation(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            lead_id=lead.id,
            agent_id=dto.agent_id,
            title=self._svc.build_title(conversation, lead.name),
            notes=notes,
            status=QuotationStatus.DRAFT,
            currency="USD",
            created_at=now,
            updated_at=now,
        )
        quotation = self._svc.apply_line_items(quotation, line_items)
        quotation = await self._quot_repo.create(quotation)

        # Index quotation in ChromaDB for future similarity matching
        await self._vs.upsert(
            collection=settings.CHROMA_COLLECTION_QUOTATIONS,
            doc_id=str(quotation.id),
            text=f"{quotation.title}\n{notes}\n"
            + "\n".join(f"{i.description} {i.unit_price}" for i in line_items),
            metadata={"lead_id": str(lead.id), "total": quotation.total_amount},
        )
        quotation.vector_id = str(quotation.id)
        quotation = await self._quot_repo.update(quotation)

        # Update conversation + lead status
        conversation.status = ConversationStatus.QUOTED
        await self._conv_repo.update(conversation)
        lead.status = LeadStatus.QUOTED
        await self._lead_repo.update(lead)

        return quotation
