"""RequirementsDoc — structured requirements extracted by the P2 Requirements Agent.

Input sources (multi-modal):
  - PDF    (pdfplumber / PyMuPDF)
  - DOCX   (python-docx)
  - PPTX   (python-pptx)
  - Excel  (openpyxl)
  - Screenshots / images (GPT-4.1 Vision)
  - Audio  (OpenAI Whisper)
  - Email threads (plain text)

After extraction (GPT-4.1 structured output), Claude Sonnet 4.6 enriches:
  - budget estimation
  - deadline inference
  - tech stack recommendations
  - lead scoring signal

Structured schema mirrors prompts/shared/output_schemas/requirements_v1.json
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class ServiceType(StrEnum):
    WEB_DEVELOPMENT = "web_development"
    MOBILE_APP = "mobile_app"
    API_INTEGRATION = "api_integration"
    DATA_ANALYTICS = "data_analytics"
    AI_ML = "ai_ml"
    DESIGN = "design"
    CONSULTING = "consulting"
    OTHER = "other"


class Platform(StrEnum):
    WEB = "web"
    IOS = "ios"
    ANDROID = "android"
    CROSS_PLATFORM = "cross_platform"
    BACKEND_ONLY = "backend_only"
    DESKTOP = "desktop"
    NOT_SPECIFIED = "not_specified"


class ExtractionStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    ENRICHED = "enriched"        # Claude Sonnet 4.6 enrichment complete
    APPROVED = "approved"        # SALES_MANAGER approved for proposal generation
    FAILED = "failed"


class RequirementsDoc(BaseModel):
    id: UUID
    lead_id: UUID
    conversation_id: UUID | None = None   # Linked if extracted from conversation

    # Source file metadata
    source_filename: str | None = None
    source_mime_type: str | None = None   # application/pdf, etc.

    # Extracted fields (GPT-4.1 structured output)
    service_type: ServiceType = ServiceType.OTHER
    platform: Platform = Platform.NOT_SPECIFIED
    features: list[str] = Field(default_factory=list)
    tech_preferences: list[str] = Field(default_factory=list)

    # Budget in USD — can be a range
    budget_min: float | None = None
    budget_max: float | None = None

    deadline_description: str | None = None   # e.g. "3 weeks", "end of Q2"
    deadline_date: datetime | None = None      # parsed absolute date if inferrable

    # Free-text notes from extraction
    raw_summary: str = ""

    # Enrichment fields (Claude Sonnet 4.6)
    enriched_summary: str = ""
    recommended_stack: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)

    # Confidence 0.0–1.0 of the extraction quality
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    status: ExtractionStatus = ExtractionStatus.PENDING

    # Qdrant vector ID in the requirements collection
    vector_id: str | None = None

    created_at: datetime
    updated_at: datetime
