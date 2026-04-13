# [OWNER: Dev 4 — Frontend, Auth & DevOps]
"""FiverrProfile — a Fiverr gig/profile owned by the agency.

Salespersons register a Fiverr profile so the system can tag incoming leads
to the correct profile without any webhook integration.  All lead creation is
manual — the salesperson sees the Fiverr message, pastes it into the UI, and
selects which profile it came from.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FiverrProfile(BaseModel):
    id: UUID
    # FIVERR_PROFILE_ID from settings — human-readable Fiverr username / gig slug
    profile_id: str

    # Display name shown in the UI when salesperson selects a profile
    display_name: str

    # Brief description of what services this profile advertises
    service_description: str = ""

    # Which agent "owns" this profile (may be re-assigned)
    owner_agent_id: UUID | None = None

    is_active: bool = True

    created_at: datetime
    updated_at: datetime
