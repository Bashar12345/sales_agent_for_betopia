# [OWNER: Bashar — Frontend, Auth & DevOps]
"""Aggregate all v1 routers into a single APIRouter.

Pipeline layout:
  P1 Conversation Engine:  /input, /suggestions
  P2 Requirements Agent:   /requirements, /proposals
  P3 Data Layer:           (async workers + NATS subscribers, no direct HTTP endpoints)

Legacy / shared:  /leads, /conversations, /quotations, /resources, /integrations/odoo
Deprecated:       /replies (kept for backwards-compat; use /input + /suggestions instead)
"""

from fastapi import APIRouter

from src.api.v1 import health
from src.api.v1.conversations import router as conversations_router
from src.api.v1.input import router as input_router
from src.api.v1.leads import router as leads_router
from src.api.v1.proposals import router as proposals_router
from src.api.v1.quotations import router as quotations_router
from src.api.v1.replies import router as replies_router
from src.api.v1.requirements import router as requirements_router
from src.api.v1.resources import router as resources_router
from src.api.v1.suggestions import router as suggestions_router
from src.api.v1.integrations.odoo import router as odoo_router

v1_router = APIRouter(prefix="/api/v1")

# ── Health ────────────────────────────────────────────────────────────────────
v1_router.include_router(health.router)

# ── P1: Conversation Engine ───────────────────────────────────────────────────
v1_router.include_router(input_router)          # POST /input/message
v1_router.include_router(suggestions_router)    # GET  /suggestions/{lead_id}

# ── P2: Requirements Agent ────────────────────────────────────────────────────
v1_router.include_router(requirements_router)   # POST /requirements/upload
v1_router.include_router(proposals_router)      # POST /proposals/generate

# ── Core entities ─────────────────────────────────────────────────────────────
v1_router.include_router(leads_router)
v1_router.include_router(conversations_router)
v1_router.include_router(quotations_router)
v1_router.include_router(resources_router)

# ── Integrations ──────────────────────────────────────────────────────────────
v1_router.include_router(odoo_router)

# ── Legacy (deprecated in v3.0 — use /input + /suggestions) ──────────────────
v1_router.include_router(replies_router)