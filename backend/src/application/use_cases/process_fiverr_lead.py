# [OWNER: Dev 3 — P2 Requirements Agent]
"""ProcessFiverrLead — ingest a Fiverr webhook and create a Lead."""

import uuid
from datetime import datetime, timezone

from src.application.ports.fiverr_port import IFiverrPort
from src.domain.entities.lead import Lead
from src.domain.repositories.lead_repository import ILeadRepository


class ProcessFiverrLeadUseCase:
    def __init__(
        self,
        lead_repo: ILeadRepository,
        fiverr_port: IFiverrPort,
    ) -> None:
        self._lead_repo = lead_repo
        self._fiverr_port = fiverr_port

    async def execute(self, raw_payload: bytes, signature: str) -> Lead:
        lead = await self._fiverr_port.parse_webhook_payload(raw_payload, signature)

        existing = None
        if lead.fiverr_order_id:
            existing = await self._lead_repo.get_by_fiverr_order_id(lead.fiverr_order_id)

        if existing:
            return existing  # idempotent — do not duplicate

        lead.id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        lead.created_at = now
        lead.updated_at = now
        return await self._lead_repo.create(lead)
