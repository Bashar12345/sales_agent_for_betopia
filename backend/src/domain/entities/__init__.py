from src.domain.entities.conversation import Conversation, ConversationStatus
from src.domain.entities.fiverr_profile import FiverrProfile
from src.domain.entities.lead import Lead, LeadSource, LeadStatus
from src.domain.entities.message import Message, MessageDirection, MessageRole
from src.domain.entities.proposal import Proposal, ProposalStatus
from src.domain.entities.quotation import LineItem, Quotation, QuotationStatus
from src.domain.entities.requirements_doc import (
    ExtractionStatus,
    Platform,
    RequirementsDoc,
    ServiceType,
)
from src.domain.entities.resource import Resource, ResourceType
from src.domain.entities.sales_agent import AgentRole, SalesAgent
from src.domain.entities.suggestion import (
    Suggestion,
    SuggestionEvent,
    SuggestionStrategy,
    SuggestionTone,
)

__all__ = [
    # Core
    "AgentRole",
    "Conversation",
    "ConversationStatus",
    "FiverrProfile",
    "Lead",
    "LeadSource",
    "LeadStatus",
    "LineItem",
    "Message",
    "MessageDirection",
    "MessageRole",
    "Quotation",
    "QuotationStatus",
    "Resource",
    "ResourceType",
    "SalesAgent",
    # P2
    "ExtractionStatus",
    "Platform",
    "Proposal",
    "ProposalStatus",
    "RequirementsDoc",
    "ServiceType",
    # P1
    "Suggestion",
    "SuggestionEvent",
    "SuggestionStrategy",
    "SuggestionTone",
]
