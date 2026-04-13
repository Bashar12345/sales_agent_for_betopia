# [OWNER: Dev 3 — P2 Requirements Agent]
"""IDocumentGeneratorPort — abstract interface for .docx quotation export."""

from abc import ABC, abstractmethod

from src.domain.entities.quotation import Quotation


class IDocumentGeneratorPort(ABC):
    @abstractmethod
    async def generate_quotation_doc(
        self,
        quotation: Quotation,
        lead_name: str,
        agent_name: str,
    ) -> str:
        """
        Render a .docx file from the quotation.
        Returns the absolute file path of the saved document.
        """
