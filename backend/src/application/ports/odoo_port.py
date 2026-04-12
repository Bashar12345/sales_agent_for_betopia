"""IOdooPort — abstract interface for Odoo ERP integration.

Populated later when the Odoo custom chatbot integration is built.
Only the contract is defined here; implementation is in infrastructure/clients/.
"""

from abc import ABC, abstractmethod

from src.domain.entities.lead import Lead
from src.domain.entities.quotation import Quotation


class IOdooPort(ABC):
    @abstractmethod
    async def sync_lead(self, lead: Lead) -> int:
        """Create or update a CRM lead in Odoo. Returns Odoo record ID."""

    @abstractmethod
    async def sync_quotation(self, quotation: Quotation, lead: Lead) -> int:
        """Create a sale.order in Odoo from the quotation. Returns Odoo record ID."""

    @abstractmethod
    async def get_connection_status(self) -> bool:
        """Ping Odoo to verify credentials are valid."""
