# [OWNER: Dev 4 — Frontend, Auth & DevOps]
"""FastAPI application entry point — Sales Intelligence Agent v3.0.

Startup sequence:
  1. Configure structured logging
  2. Initialise Qdrant collections (HNSW + scalar quantisation)
  3. Connect to NATS JetStream
  4. Create PostgreSQL tables (dev) / verify connection (prod)
  5. Register all v1 routes
  6. Register exception handlers
  7. Mount Prometheus metrics middleware

Shutdown: drain NATS, dispose PostgreSQL connection pool.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from src.api.v1.router import v1_router
from src.core.exceptions import (
    DocumentGenerationError,
    EventBusError,
    ForbiddenError,
    LLMError,
    NotFoundError,
    OdooIntegrationError,
    RequirementsExtractionError,
    SuggestionGenerationError,
    UnauthorizedError,
    ValidationError,
    VectorStoreError,
)
from src.core.logging import configure_logging
from src.core.settings import settings
from src.infrastructure.clients.nats_client import NATSClient
from src.infrastructure.clients.qdrant_client import QdrantVectorClient
from src.infrastructure.db.base import Base
from src.infrastructure.db.session import engine

log = structlog.get_logger()

# Singleton NATS client shared across the app lifecycle
_nats_client = NATSClient()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging(debug=settings.DEBUG)
    log.info("startup.begin", version="3.0.0", env=settings.APP_ENV)

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    if settings.APP_ENV in ("development", "testing"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info("db.tables_synced")

    # ── Qdrant collections ────────────────────────────────────────────────────
    try:
        qdrant = QdrantVectorClient()
        await qdrant.ensure_collections()
        log.info("qdrant.ready")
    except Exception as exc:
        log.warning("qdrant.init_failed", error=str(exc))

    # ── NATS JetStream ────────────────────────────────────────────────────────
    try:
        await _nats_client.connect()
        # Make the NATS client available via app state for WebSocket endpoints
        app.state.nats = _nats_client
        log.info("nats.ready")
    except Exception as exc:
        log.warning("nats.init_failed", error=str(exc))

    log.info("startup.complete")
    yield

    # ── Graceful shutdown ─────────────────────────────────────────────────────
    log.info("shutdown.begin")
    await _nats_client.close()
    await engine.dispose()
    log.info("shutdown.complete")


app = FastAPI(
    title=settings.APP_NAME,
    version="3.0.0",
    description=(
        "Sales Intelligence Agent v3.0 — "
        "P1 Conversation Engine, P2 Requirements Agent, P3 Data Layer. "
        "PostgreSQL 17 + Qdrant 1.13 + NATS JetStream + GPT-4.1/Claude Sonnet 4.6 fallback chain."
    ),
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["https://your-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Prometheus metrics ────────────────────────────────────────────────────────
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(v1_router)


# ── Health check (used by Docker healthcheck + Kubernetes liveness probe) ─────
@app.get("/health", tags=["ops"])
async def health() -> dict:
    return {"status": "ok", "version": "3.0.0"}


# ── Exception handlers ────────────────────────────────────────────────────────
@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ValidationError)
async def validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(UnauthorizedError)
async def unauthorized_handler(request: Request, exc: UnauthorizedError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(ForbiddenError)
async def forbidden_handler(request: Request, exc: ForbiddenError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(LLMError)
async def llm_handler(request: Request, exc: LLMError) -> JSONResponse:
    log.error("llm.error", detail=str(exc))
    return JSONResponse(status_code=503, content={"detail": f"LLM unavailable: {exc}"})


@app.exception_handler(SuggestionGenerationError)
async def suggestion_handler(request: Request, exc: SuggestionGenerationError) -> JSONResponse:
    log.error("p1.suggestion_error", detail=str(exc))
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(RequirementsExtractionError)
async def requirements_handler(
    request: Request, exc: RequirementsExtractionError
) -> JSONResponse:
    log.error("p2.extraction_error", detail=str(exc))
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(VectorStoreError)
async def vector_store_handler(request: Request, exc: VectorStoreError) -> JSONResponse:
    log.error("qdrant.error", detail=str(exc))
    return JSONResponse(status_code=503, content={"detail": f"Vector store error: {exc}"})


@app.exception_handler(EventBusError)
async def event_bus_handler(request: Request, exc: EventBusError) -> JSONResponse:
    log.error("nats.error", detail=str(exc))
    return JSONResponse(status_code=503, content={"detail": f"Event bus error: {exc}"})


@app.exception_handler(OdooIntegrationError)
async def odoo_handler(request: Request, exc: OdooIntegrationError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": f"Odoo error: {exc}"})


@app.exception_handler(DocumentGenerationError)
async def doc_handler(request: Request, exc: DocumentGenerationError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})