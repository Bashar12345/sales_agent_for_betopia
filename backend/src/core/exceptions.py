# [OWNER: Dev 1 — Data Foundation (P3)]
"""Domain + HTTP exception hierarchy.

Domain exceptions are raised in the domain/application layers (no HTTP knowledge).
FastAPI exception handlers in main.py map them to HTTP responses.
"""


class AppError(Exception):
    """Root of all application exceptions."""


# ── Domain ────────────────────────────────────────────────────────────────────
class NotFoundError(AppError):
    """Resource not found in the database."""


class AlreadyExistsError(AppError):
    """Attempt to create a duplicate resource."""


class ValidationError(AppError):
    """Business-rule validation failure."""


class UnauthorizedError(AppError):
    """Actor does not have the required role for this action."""


class ForbiddenError(AppError):
    """Actor authenticated but not permitted to access this resource."""


# ── Pipeline ──────────────────────────────────────────────────────────────────
class IntentClassificationError(AppError):
    """Intent classifier returned an unrecognised label."""


class SuggestionGenerationError(AppError):
    """P1 pipeline failed to produce reply suggestions."""


class RequirementsExtractionError(AppError):
    """P2 pipeline failed to extract structured requirements from a document."""


# ── Integration ───────────────────────────────────────────────────────────────
class LLMError(AppError):
    """All providers in the fallback chain failed (GPT-4.1 → Claude → vLLM)."""


class LLMTimeoutError(LLMError):
    """Primary provider exceeded the timeout threshold; fallback triggered."""


class VectorStoreError(AppError):
    """Qdrant operation failed."""


class EventBusError(AppError):
    """NATS JetStream publish or subscribe failed."""


class OdooIntegrationError(AppError):
    """Odoo XML-RPC call failed (future ERP integration)."""


class DocumentGenerationError(AppError):
    """Failed to build a quotation .docx or proposal PDF."""