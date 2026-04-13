# [OWNER: Dev 1 — Data Foundation (P3)]
"""SQLAlchemy ORM model for Quotation — PostgreSQL 17.

Line items are stored as JSONB for efficient partial-field querying.
"""

import uuid
from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.quotation import QuotationStatus
from src.infrastructure.db.base import Base
from src.infrastructure.db.models.mixins import TimestampMixin


class QuotationModel(TimestampMixin, Base):
    __tablename__ = "quotations"

    id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    conversation_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=False), ForeignKey("conversations.id"), nullable=False, index=True
    )
    lead_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=False), ForeignKey("leads.id"), nullable=False, index=True
    )
    agent_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=False), ForeignKey("sales_agents.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    line_items: Mapped[Any] = mapped_column(JSONB, nullable=False, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    status: Mapped[str] = mapped_column(
        PgEnum("draft", "under_review", "sent", "accepted", "rejected",
               name="quotationstatus", create_type=False),
        nullable=False, default=QuotationStatus.DRAFT.value, index=True,
    )
    doc_path: Mapped[str | None] = mapped_column(String(512))
    vector_id: Mapped[str | None] = mapped_column(String(64))
    odoo_order_id: Mapped[int | None] = mapped_column(Integer)
