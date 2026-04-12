"""IFiverrPort — abstract interface for Fiverr webhook ingestion."""

from abc import ABC, abstractmethod

from src.domain.entities.lead import Lead


class IFiverrPort(ABC):
    @abstractmethod
    async def parse_webhook_payload(self, raw_payload: bytes, signature: str) -> Lead:
        """
        Validate the Fiverr HMAC signature and parse the payload into a Lead.
        Raises FiverrWebhookError on bad signature or unrecognised schema.
        """
