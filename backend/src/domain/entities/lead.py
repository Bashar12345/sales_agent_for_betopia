# [OWNER: Bashar — Frontend, Auth & DevOps]
"""Lead — a potential customer sourced from Fiverr (manually entered by salesperson).

No webhook integration — salesperson pastes the customer message into the UI.
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class LeadStatus(StrEnum):
    NEW = "new"
    IN_CONVERSATION = "in_conversation"
    QUOTED = "quoted"        # Proposal has been generated
    WON = "won"
    LOST = "lost"


class LeadSource(StrEnum):
    FIVERR = "fiverr"
    MANUAL = "manual"        # Added directly by a sales agent


class Lead(BaseModel):
    id: UUID
    # Fiverr identifiers — populated when salesperson registers the lead
    fiverr_order_id: str | None = None
    fiverr_buyer_username: str | None = None
    # profile_id links this lead to a specific Fiverr profile/gig
    profile_id: UUID | None = None

    name: str
    email: str | None = None
    budget: float | None = None           # Stated budget in USD

    # Free-text summary; enriched by P2 Requirements Agent
    requirement_summary: str

    status: LeadStatus = LeadStatus.NEW
    source: LeadSource = LeadSource.FIVERR

    assigned_agent_id: UUID | None = None

    # Lead quality score 0–100 (computed by P2 enrichment, Claude Sonnet 4.6)
    score: int = 0

    # Intent label from the latest P1 classification
    intent_label: str | None = None

    # Populated after Odoo ERP sync (future)
    erp_record_id: str | None = None

    created_at: datetime
    updated_at: datetime
