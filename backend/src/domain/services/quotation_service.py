# [OWNER: Akash — P2 Requirements Agent]
"""QuotationService — pure business logic for building a Quotation.

No LLM calls here. LLM integration lives in the application layer
(use cases) via the ILLMPort. This service only applies business rules
once the LLM has already returned structured data.
"""

from src.domain.entities.conversation import Conversation
from src.domain.entities.quotation import LineItem, Quotation, QuotationStatus


class QuotationService:
    def build_title(self, conversation: Conversation, lead_name: str) -> str:
        return f"Quotation for {lead_name}"

    def validate_line_items(self, items: list[LineItem]) -> list[str]:
        """Returns a list of validation error messages (empty = valid)."""
        errors: list[str] = []
        for idx, item in enumerate(items):
            if item.unit_price < 0:
                errors.append(f"Item {idx + 1} '{item.description}': price cannot be negative")
            if item.quantity <= 0:
                errors.append(f"Item {idx + 1} '{item.description}': quantity must be > 0")
        return errors

    def apply_line_items(self, quotation: Quotation, items: list[LineItem]) -> Quotation:
        quotation.line_items = items
        quotation.compute_total()
        return quotation

    def mark_sent(self, quotation: Quotation) -> Quotation:
        if quotation.status != QuotationStatus.DRAFT:
            raise ValueError(f"Cannot send quotation in status: {quotation.status}")
        quotation.status = QuotationStatus.SENT
        return quotation
