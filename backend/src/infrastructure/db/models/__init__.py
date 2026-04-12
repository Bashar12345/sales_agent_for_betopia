# Import all models here so Alembic autogenerate picks them up
from src.infrastructure.db.models.conversation_model import ConversationModel, MessageModel
from src.infrastructure.db.models.lead_model import LeadModel
from src.infrastructure.db.models.quotation_model import QuotationModel
from src.infrastructure.db.models.resource_model import ResourceModel
from src.infrastructure.db.models.sales_agent_model import SalesAgentModel

__all__ = [
    "ConversationModel",
    "LeadModel",
    "MessageModel",
    "QuotationModel",
    "ResourceModel",
    "SalesAgentModel",
]
