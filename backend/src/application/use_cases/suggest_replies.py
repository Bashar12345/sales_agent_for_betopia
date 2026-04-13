# [OWNER: Niloy — P1 Conversation Engine]
"""SuggestReplies — salesman tool: customer message → reply candidates.

Steps:
  1. If a conversation_id is given, load recent messages for context
  2. Query ChromaDB for similar past conversations + resources
  3. Call LLM for reply candidates
  4. Apply domain filtering (ReplyService)
"""

from src.application.dto.reply_dto import ReplySuggestionsResponseDTO, SuggestRepliesDTO
from src.application.ports.llm_port import ILLMPort
from src.application.ports.vector_store_port import IVectorStorePort
from src.core.settings import settings
from src.domain.repositories.conversation_repository import IConversationRepository
from src.domain.services.reply_service import ReplyService


class SuggestRepliesUseCase:
    def __init__(
        self,
        conversation_repo: IConversationRepository,
        llm_port: ILLMPort,
        vector_store: IVectorStorePort,
        reply_service: ReplyService,
    ) -> None:
        self._conv_repo = conversation_repo
        self._llm = llm_port
        self._vs = vector_store
        self._svc = reply_service

    async def execute(self, dto: SuggestRepliesDTO) -> ReplySuggestionsResponseDTO:
        recent_messages = []
        if dto.conversation_id:
            conversation = await self._conv_repo.get_by_id(dto.conversation_id)
            if conversation:
                recent_messages = self._svc.build_context_window(conversation.messages)

        similar_convs = await self._vs.query_similar(
            settings.CHROMA_COLLECTION_CONVERSATIONS,
            dto.customer_message,
            n_results=5,
        )
        resources = await self._vs.query_similar(
            settings.CHROMA_COLLECTION_RESOURCES,
            dto.customer_message,
            n_results=3,
        )

        raw_replies = await self._llm.suggest_replies(
            customer_message=dto.customer_message,
            recent_messages=recent_messages,
            similar_conversations=[d["text"] for d in similar_convs],
            resources_context=[d["text"] for d in resources],
        )

        filtered = self._svc.filter_replies(raw_replies)
        return ReplySuggestionsResponseDTO(
            suggestions=filtered,
            conversation_id=dto.conversation_id,
        )
