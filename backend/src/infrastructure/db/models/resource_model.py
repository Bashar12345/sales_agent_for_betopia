# [OWNER: Dev 1 — Data Foundation (P3)]
"""SQLAlchemy ORM model for Resource (uploaded knowledge-base documents) — PostgreSQL 17."""

import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.resource import ResourceType
from src.infrastructure.db.base import Base
from src.infrastructure.db.models.mixins import TimestampMixin


class ResourceModel(TimestampMixin, Base):
    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(Enum(ResourceType), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # PostgreSQL TEXT has no length limit
    file_path: Mapped[str | None] = mapped_column(String(512))
    original_filename: Mapped[str | None] = mapped_column(String(255))
    vector_id: Mapped[str | None] = mapped_column(String(64))
    uploaded_by_agent_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=False), ForeignKey("sales_agents.id"), nullable=False
    )
