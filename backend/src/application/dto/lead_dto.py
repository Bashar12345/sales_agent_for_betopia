# [OWNER: Dev 4 — Frontend, Auth & DevOps]
from uuid import UUID

from pydantic import BaseModel

from src.domain.entities.lead import LeadSource, LeadStatus


class CreateLeadDTO(BaseModel):
    name: str
    email: str | None = None
    fiverr_order_id: str | None = None
    fiverr_buyer_username: str | None = None
    budget: float | None = None
    requirement_summary: str
    source: LeadSource = LeadSource.FIVERR
    assigned_agent_id: UUID | None = None


class UpdateLeadStatusDTO(BaseModel):
    status: LeadStatus
