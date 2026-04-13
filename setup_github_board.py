#!/usr/bin/env python3
"""
setup_github_board.py — Sales Intelligence Agent v3.0
Creates GitHub labels, milestones, and issues for all 4 AI agent workstreams.

Usage:
    python setup_github_board.py                  # create everything
    python setup_github_board.py --dry-run        # print what would be created
    python setup_github_board.py --labels-only    # create labels + milestones only
    python setup_github_board.py --issues-only    # skip labels/milestones
"""

import argparse
import subprocess
import sys
from dataclasses import dataclass


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Issue:
    title: str
    body: str
    labels: list[str]
    milestone: str


# ─────────────────────────────────────────────────────────────────────────────
# Labels
# ─────────────────────────────────────────────────────────────────────────────

LABELS: list[tuple[str, str, str]] = [
    # Priority
    ("P1-Blocker",               "B60205", "Blocks other agents — must land first"),
    ("P2-Core",                  "D93F0B", "Core pipeline implementation task"),
    ("P3-Quality",               "0E8A16", "Observability, evals, quality, polish"),
    # Ownership
    ("Dev1-DataFoundation",      "1D76DB", "Owner: Dev 1 — Data Foundation (P3 pipeline)"),
    ("Dev2-ConversationEngine",  "5319E7", "Owner: Dev 2 — P1 Conversation Engine"),
    ("Dev3-RequirementsAgent",   "006B75", "Owner: Dev 3 — P2 Requirements Agent"),
    ("Dev4-FrontendAuth",        "FBCA04", "Owner: Dev 4 — Frontend, Auth & DevOps"),
    # State
    ("blocked",                  "E4E669", "Waiting on a deliverable from another agent"),
    ("in-progress",              "0052CC", "Currently being implemented"),
    ("needs-review",             "D4C5F9", "Implementation done — needs code review"),
]

# ─────────────────────────────────────────────────────────────────────────────
# Milestones
# ─────────────────────────────────────────────────────────────────────────────

MILESTONES: list[tuple[str, str]] = [
    (
        "Foundation",
        "Dev 1 infra + frozen port contracts landed — all agents can start coding",
    ),
    (
        "P1-Live",
        "P1 suggestion pipeline end-to-end; POST /input p95 < 5 s",
    ),
    (
        "P2-Live",
        "P2 requirements → quotation → PDF proposal pipeline end-to-end",
    ),
    (
        "Production",
        "Auth, frontend, CI/CD, K8s manifests — ready to ship",
    ),
]

# ─────────────────────────────────────────────────────────────────────────────
# Issues
# ─────────────────────────────────────────────────────────────────────────────

ISSUES: list[Issue] = [

    # ── Dev 1 — BLOCKING ────────────────────────────────────────────────────

    Issue(
        title="[Dev1] B1 — docker-compose.yml: start all 5 local services",
        body=(
            "**Owner:** Dev 1 — Data Foundation\n"
            "**Blocks:** Dev 2, Dev 3, Dev 4 — nobody can run the stack locally without this\n\n"
            "## Services required\n"
            "| Service | Image | Host port |\n"
            "|---------|-------|-----------|\n"
            "| PostgreSQL 17 | `postgres:17-alpine` | 5433 |\n"
            "| Redis 7.4 | `redis:7.4-alpine` | 6379 |\n"
            "| Qdrant 1.13 | `qdrant/qdrant:v1.13.6` | 6333 (REST) 6334 (gRPC) |\n"
            "| NATS JetStream 2.10 | `nats:2.10-alpine` | 4222 / 8222 |\n"
            "| MinIO | `minio/minio:latest` | 9000 / 9001 |\n\n"
            "All services must have healthchecks.\n\n"
            "## Acceptance\n"
            "```bash\n"
            "docker compose -f backend/deploy/docker-compose.yml up -d\n"
            "docker compose -f backend/deploy/docker-compose.yml ps\n"
            "# → all 5 containers show (healthy)\n"
            "```\n\n"
            "**File:** `backend/deploy/docker-compose.yml`\n"
            "_See_ `backend/instruction_dev1.md` § B1"
        ),
        labels=["P1-Blocker", "Dev1-DataFoundation"],
        milestone="Foundation",
    ),

    Issue(
        title="[Dev1] B2 — postgres/init.sql: all 9 tables, enums, indexes, triggers",
        body=(
            "**Owner:** Dev 1 — Data Foundation\n"
            "**Blocks:** Dev 2 (needs conversations/messages), Dev 3 (needs requirements_docs/proposals)\n\n"
            "## Table creation order (no FK violations)\n"
            "```\n"
            "sales_agents\n"
            "  └─ leads\n"
            "       └─ conversations\n"
            "            ├─ messages\n"
            "            └─ quotations\n"
            "                  └─ requirements_docs\n"
            "                         └─ proposals\n"
            "resources        (standalone)\n"
            "outbox_events    (partitioned by created_at)\n"
            "```\n\n"
            "## Also required\n"
            "- 8 enum types: `lead_status`, `lead_source`, `conv_status`, `msg_role`, "
            "`quot_status`, `res_type`, `agent_role`, `prop_status`\n"
            "- Indexes: `idx_quotations_line_items` (GIN/JSONB), `idx_resources_name_trgm` "
            "(GIN/trigram), `idx_outbox_unpublished` (partial WHERE published = FALSE), plus all FK indexes\n"
            "- `set_updated_at()` trigger applied to all tables with `updated_at`\n\n"
            "## Acceptance\n"
            "```bash\n"
            "psql -U betopia -d betopia -c '\\dt'\n"
            "# → 9 rows listed\n"
            "```\n\n"
            "**File:** `backend/deploy/postgres/init.sql`\n"
            "_See_ `backend/instruction_dev1.md` § B2"
        ),
        labels=["P1-Blocker", "Dev1-DataFoundation"],
        milestone="Foundation",
    ),

    Issue(
        title="[Dev1] B3 — Freeze port interfaces: IVectorStorePort, IEmbeddingPort, ILLMPort, IEventBusPort",
        body=(
            "**Owner:** Dev 1 — Data Foundation\n"
            "**Blocks:** Dev 2 and Dev 3 code against these — signatures must not change after this closes\n\n"
            "## Frozen contracts\n"
            "| File | Interface | Signature summary |\n"
            "|------|-----------|-------------------|\n"
            "| `ports/vector_store_port.py` | `IVectorStorePort` | `upsert(collection, doc_id, text, metadata, vector)` · `query_similar(collection, query_vector, n_results, filters)` · `delete` |\n"
            "| `ports/embedding_port.py` | `IEmbeddingPort` | `embed_text(text) -> list[float]` · `embed_batch(texts)` |\n"
            "| `ports/llm_port.py` | `ILLMPort` | `generate_quotation_items(transcript, similar_quotations, resources_context)` · `suggest_replies(...)` |\n"
            "| `ports/event_bus_port.py` | `IEventBusPort` | `publish(subject, event_type, payload, source)` · `close()` |\n\n"
            "## Acceptance\n"
            "- All 4 files importable without error\n"
            "- `isinstance(QdrantVectorClient(), IVectorStorePort)` → `True`\n"
            "- Any future change requires a `# BREAKING CHANGE:` comment + PR description\n\n"
            "_See_ `backend/instruction_dev1.md` § B3"
        ),
        labels=["P1-Blocker", "Dev1-DataFoundation"],
        milestone="Foundation",
    ),

    Issue(
        title="[Dev1] T1 — QdrantVectorClient: 3 collections, HNSW + INT8 quantisation",
        body=(
            "**Owner:** Dev 1\n\n"
            "## Acceptance\n"
            "- `ensure_collections()` creates `conversations`, `requirements`, `pricing`\n"
            "- All collections: COSINE, 3072-dim, INT8 scalar quant `always_ram=True`\n"
            "- `conversations` + `requirements`: m=16, ef=128; `pricing`: m=8, ef=64\n"
            "- Round-trip: `upsert` → `query_similar` returns the doc\n"
            "- `prefer_grpc=True`\n\n"
            "**File:** `src/infrastructure/clients/qdrant_client.py`"
        ),
        labels=["P2-Core", "Dev1-DataFoundation"],
        milestone="Foundation",
    ),

    Issue(
        title="[Dev1] T2 — RedisCacheClient: suggestion + embedding + rate-limit caches",
        body=(
            "**Owner:** Dev 1\n\n"
            "## Methods\n"
            "```python\n"
            "get_suggestions(conversation_id, message) -> list[str] | None\n"
            "set_suggestions(conversation_id, message, suggestions, ttl=300)\n"
            "get_embedding(text, model) -> list[float] | None\n"
            "set_embedding(text, model, vector, ttl=86400)\n"
            "check_rate_limit(agent_id, limit=60) -> bool\n"
            "close()\n"
            "```\n\n"
            "## Acceptance\n"
            "- Cache keys: SHA-256 of inputs\n"
            "- Suggestion TTL 300 s, embedding TTL 86 400 s\n"
            "- `check_rate_limit` uses Redis INCR + EXPIRE\n\n"
            "**File:** `src/infrastructure/clients/redis_cache_client.py`"
        ),
        labels=["P2-Core", "Dev1-DataFoundation"],
        milestone="Foundation",
    ),

    Issue(
        title="[Dev1] T3 — NATSClient: CloudEvents 1.0 publish via JetStream",
        body=(
            "**Owner:** Dev 1\n\n"
            "## Acceptance\n"
            "- Implements `IEventBusPort`\n"
            "- Every published message wrapped in CloudEvents 1.0 envelope "
            "(specversion, type, source, id=uuid4, time, datacontenttype, data)\n"
            "- `close()` drains before disconnect\n\n"
            "**File:** `src/infrastructure/clients/nats_client.py`"
        ),
        labels=["P2-Core", "Dev1-DataFoundation"],
        milestone="Foundation",
    ),

    Issue(
        title="[Dev1] T4 — indexing_worker: index_conversation + re_embed_collection (p3-batch)",
        body=(
            "**Owner:** Dev 1\n\n"
            "## `index_conversation` task\n"
            "Queue: `p3-batch` · max_retries=3 · countdown=60\n"
            "Steps: load conv → `embed_text(transcript)` → `QdrantVectorClient.upsert(CONVERSATIONS, ...)` → set `conv.vector_id` → commit\n\n"
            "## `re_embed_collection` task\n"
            "Queue: `p3-batch`\n"
            "Re-embeds all rows where `vector_id IS NOT NULL` for a given Qdrant collection.\n\n"
            "## Acceptance\n"
            "- After task runs: `conv.vector_id` set, Qdrant `query_similar` returns the conversation\n\n"
            "**File:** `src/workers/indexing_worker.py`"
        ),
        labels=["P2-Core", "Dev1-DataFoundation"],
        milestone="Foundation",
    ),

    Issue(
        title="[Dev1] T5 — Celery factory: p1-high, p2-normal, p3-batch queues",
        body=(
            "**Owner:** Dev 1\n\n"
            "## Acceptance\n"
            "- `celery_app` exposes 3 queues: `p1-high`, `p2-normal`, `p3-batch`\n"
            "- Do NOT register Dev 2 or Dev 3 tasks in this file\n"
            "- Other agents import `celery_app` and register their own tasks\n\n"
            "**File:** `src/workers/celery_app.py`"
        ),
        labels=["P2-Core", "Dev1-DataFoundation"],
        milestone="Foundation",
    ),

    Issue(
        title="[Dev1] T6 — GET /health: check PG + Redis + Qdrant + NATS",
        body=(
            "**Owner:** Dev 1\n\n"
            "## Acceptance\n"
            "- `200` when all 4 reachable\n"
            "- `503` + partial JSON when any is down\n"
            "- Response shape: `{ postgres, redis, qdrant, nats }` each `ok | error`\n\n"
            "**File:** `src/api/v1/health.py`"
        ),
        labels=["P3-Quality", "Dev1-DataFoundation"],
        milestone="Foundation",
    ),

    # ── Dev 2 — P1 Conversation Engine ──────────────────────────────────────

    Issue(
        title="[Dev2] LLM client: GPT-4.1 → Claude Sonnet 4.6 → vLLM fallback chain",
        body=(
            "**Owner:** Dev 2 — P1 Conversation Engine\n"
            "**Depends on:** Dev 1 B3 (port interfaces frozen)\n\n"
            "## Acceptance\n"
            "- Implements `ILLMPort` + `IEmbeddingPort`\n"
            "- Fallback: GPT-4.1 → (>3 s timeout) → Claude Sonnet 4.6 → (timeout) → vLLM\n"
            "- Tenacity: max 2 retries per provider before falling back\n"
            "- `suggest_replies` returns structured JSON matching `suggestion_list_v1.json` — no regex\n"
            "- `embed_text` checks Redis embedding cache before calling OpenAI\n"
            "- When `OPENAI_API_KEY` invalid → Claude used automatically\n\n"
            "**Files:** `src/infrastructure/clients/llm_client.py`, `vllm_client.py`, `anthropic_client.py`\n"
            "_See_ `backend/instruction_dev2.md`"
        ),
        labels=["P1-Blocker", "Dev2-ConversationEngine", "blocked"],
        milestone="P1-Live",
    ),

    Issue(
        title="[Dev2] SuggestReplies use case: 9-step P1 pipeline with Redis + Qdrant",
        body=(
            "**Owner:** Dev 2\n"
            "**Depends on:** Dev 1 QdrantVectorClient + RedisCacheClient + NATSClient\n\n"
            "## Pipeline steps\n"
            "1. Redis cache check → return on HIT\n"
            "2. Load last 10 messages from DB\n"
            "3. `embed_text(customer_message)` → vector\n"
            "4. `query_similar(QDRANT_COLLECTION_CONVERSATIONS, vector, n_results=5)`\n"
            "5. `query_similar(QDRANT_COLLECTION_PRICING, vector, n_results=3)`\n"
            "6. `llm.suggest_replies(...)` → 5 structured suggestions\n"
            "7. Redis cache SET (TTL 300 s)\n"
            "8. NATS publish `conversations.updated`\n"
            "9. Return `SuggestionListDTO`\n\n"
            "## Acceptance\n"
            "- Always returns exactly 5 suggestions\n"
            "- P95 < 5 000 ms cold, < 500 ms cache hit\n"
            "- Cache hit rate ≥ 40 % after 100 requests\n\n"
            "**File:** `src/application/use_cases/suggest_replies.py`"
        ),
        labels=["P1-Blocker", "Dev2-ConversationEngine", "blocked"],
        milestone="P1-Live",
    ),

    Issue(
        title="[Dev2] API routes: POST /input + conversations CRUD (6 endpoints)",
        body=(
            "**Owner:** Dev 2\n"
            "**Depends on:** Dev 4 `require_auth`\n\n"
            "```\n"
            "POST   /api/v1/input                    → SuggestionListDTO\n"
            "GET    /api/v1/suggestions/{conv_id}    → cached suggestions\n"
            "GET    /api/v1/conversations             → list for current agent\n"
            "GET    /api/v1/conversations/{id}        → detail + messages\n"
            "POST   /api/v1/conversations             → create for a lead\n"
            "PATCH  /api/v1/conversations/{id}        → update status\n"
            "```\n\n"
            "All routes: `Depends(require_auth)`.\n"
            "PATCH `status=closed` → enqueue `index_conversation.apply_async(queue='p3-batch')`.\n\n"
            "**Files:** `src/api/v1/input.py`, `suggestions.py`, `conversations.py`"
        ),
        labels=["P2-Core", "Dev2-ConversationEngine", "blocked"],
        milestone="P1-Live",
    ),

    Issue(
        title="[Dev2] P1 prompt eval suite: ≥10 test cases, CI-gated",
        body=(
            "**Owner:** Dev 2\n\n"
            "## Acceptance\n"
            "- `prompts/p1_suggestion/eval_suite.yaml` has ≥ 10 test cases\n"
            "- Each case: `input`, `expected_tone`, `min_confidence`\n"
            "- CI step: `pytest prompts/ -k eval_suite` must pass on every PR\n"
            "- Pass rate ≥ 90 % required to merge any prompt change\n"
            "- All prompt YAMLs have `version` field — increment before any edit\n\n"
            "**Directory:** `prompts/p1_suggestion/`"
        ),
        labels=["P3-Quality", "Dev2-ConversationEngine"],
        milestone="P1-Live",
    ),

    # ── Dev 3 — P2 Requirements Agent ───────────────────────────────────────

    Issue(
        title="[Dev3] Create ORM models: requirements_doc_model.py + proposal_model.py",
        body=(
            "**Owner:** Dev 3 — P2 Requirements Agent\n"
            "**Depends on:** Dev 1 B2 (tables must exist in PostgreSQL)\n\n"
            "## requirements_doc_model.py\n"
            "Table: `requirements_docs`\n"
            "Columns: `id (PGUUID PK)` · `conversation_id (FK)` · `lead_id (FK)` · "
            "`raw_extraction (JSONB)` · `enriched_data (JSONB)` · `budget_estimate (NUMERIC)` · "
            "`confidence_score (NUMERIC 5,4)` · `created_at` · `updated_at`\n\n"
            "## proposal_model.py\n"
            "Table: `proposals`\n"
            "Columns: `id (PGUUID PK)` · `quotation_id (FK)` · `requirements_doc_id (FK nullable)` · "
            "`lead_id (FK)` · `agent_id (FK)` · `title` · `executive_summary` · `valid_days` · "
            "`status (prop_status enum)` · `pdf_path` · `download_token` · `odoo_order_id` · "
            "`created_at` · `updated_at`\n\n"
            "## Acceptance\n"
            "- Both models importable without error\n"
            "- Use `PGUUID(as_uuid=False)` for all UUID columns\n"
            "- Import base from `src.infrastructure.db.base`\n\n"
            "**Files to create:**\n"
            "- `src/infrastructure/db/models/requirements_doc_model.py`\n"
            "- `src/infrastructure/db/models/proposal_model.py`\n"
            "- `src/infrastructure/db/repositories/requirements_doc_repository_impl.py`\n"
            "- `src/infrastructure/db/repositories/proposal_repository_impl.py`\n"
            "_See_ `backend/instruction_dev3.md`"
        ),
        labels=["P1-Blocker", "Dev3-RequirementsAgent", "blocked"],
        milestone="P2-Live",
    ),

    Issue(
        title="[Dev3] extract_requirements + enrich_requirements Celery tasks (p2-normal)",
        body=(
            "**Owner:** Dev 3\n"
            "**Depends on:** Dev 1 Qdrant + NATS + tables\n\n"
            "## extract_requirements\n"
            "Queue: `p2-normal` · max_retries=3\n"
            "1. Load conversation transcript\n"
            "2. Embed → Qdrant similarity on `requirements` collection\n"
            "3. LLM structured extraction → `RequirementsDoc` (schema: `requirements_v1.json`)\n"
            "4. Persist `RequirementsDocModel`\n"
            "5. Upsert into Qdrant `requirements` collection\n"
            "6. Enqueue `enrich_requirements`\n"
            "7. Publish NATS `requirements.extracted`\n\n"
            "## enrich_requirements\n"
            "Queue: `p2-normal` · max_retries=3\n"
            "1. LLM enrichment → `confidence_score`, `clarifying_questions`, `risk_flags`\n"
            "2. Budget estimate via `QDRANT_COLLECTION_PRICING` lookup\n"
            "3. Update model\n"
            "4. Enqueue `generate_quotation_doc`\n\n"
            "**File:** `src/workers/quotation_worker.py`"
        ),
        labels=["P2-Core", "Dev3-RequirementsAgent", "blocked"],
        milestone="P2-Live",
    ),

    Issue(
        title="[Dev3] generate_quotation use case + generate_quotation_doc Celery task",
        body=(
            "**Owner:** Dev 3\n\n"
            "## generate_quotation (POST /api/v1/quotations/generate)\n"
            "1. LLM structured output → `list[LineItem]` + executive summary\n"
            "   Schema: `prompts/shared/output_schemas/quotation_line_items_v1.json`\n"
            "2. Persist `QuotationModel` (`total_amount` = sum of line items)\n"
            "3. Index into `QDRANT_COLLECTION_PRICING`\n"
            "4. Trigger `generate_quotation_doc` Celery task\n\n"
            "## generate_quotation_doc (p2-normal)\n"
            "1. Load Quotation + RequirementsDoc + Lead\n"
            "2. `document_generator.generate_proposal_pdf(...)` → file path\n"
            "3. Persist `ProposalModel` (status=ready)\n"
            "4. Emit NATS `quotations.generated`\n\n"
            "## Acceptance\n"
            "- `total_amount` = sum of line_items unit_price × quantity\n"
            "- `ProposalModel.pdf_path` points to a real file\n"
            "- NATS event delivered\n\n"
            "**Files:** `src/application/use_cases/generate_quotation.py`, "
            "`src/infrastructure/clients/document_generator.py`"
        ),
        labels=["P2-Core", "Dev3-RequirementsAgent", "blocked"],
        milestone="P2-Live",
    ),

    Issue(
        title="[Dev3] Resource upload: PDF/DOCX/URL parse → MinIO + Qdrant index",
        body=(
            "**Owner:** Dev 3\n\n"
            "## Flow — POST /api/v1/resources/upload (multipart)\n"
            "1. Parse: PDF → pdfplumber · DOCX → python-docx · URL → httpx fetch\n"
            "2. Store binary in MinIO (bucket: `resources`)\n"
            "3. Persist `ResourceModel` (content = extracted text)\n"
            "4. Embed + upsert into `QDRANT_COLLECTION_REQUIREMENTS`\n\n"
            "**File:** `src/application/use_cases/upload_resource.py`"
        ),
        labels=["P3-Quality", "Dev3-RequirementsAgent"],
        milestone="P2-Live",
    ),

    Issue(
        title="[Dev3] P2 prompt eval suite + quotation_line_items_v1.json schema",
        body=(
            "**Owner:** Dev 3\n\n"
            "## Deliverables\n"
            "1. `prompts/shared/output_schemas/quotation_line_items_v1.json`:\n"
            "   ```json\n"
            '   {"line_items": [{"description": "", "quantity": 1, "unit_price": 0.0, "category": ""}], "executive_summary": ""}\n'
            "   ```\n"
            "2. `prompts/p2_extraction/eval_suite.yaml` with ≥ 10 extraction test cases\n"
            "3. All p2 prompts have `version` field — increment before any edit\n\n"
            "CI must run eval suite on every PR touching `prompts/p2_extraction/`."
        ),
        labels=["P3-Quality", "Dev3-RequirementsAgent"],
        milestone="P2-Live",
    ),

    # ── Dev 4 — Frontend, Auth & DevOps ─────────────────────────────────────

    Issue(
        title="[Dev4] security.py: require_auth + require_role (RS256 JWT) — LAND FIRST",
        body=(
            "**Owner:** Dev 4 — Frontend, Auth & DevOps\n"
            "**Blocks:** Dev 2 and Dev 3 — cannot protect any route without this\n\n"
            "## require_auth\n"
            "```python\n"
            "async def require_auth(\n"
            "    token: str = Depends(oauth2_scheme),\n"
            "    db: AsyncSession = Depends(get_db),\n"
            ") -> SalesAgent:\n"
            "    # Validate RS256 JWT → 401 if invalid/expired\n"
            "    # Load SalesAgent → 403 if is_active=False\n"
            "```\n\n"
            "## require_role(required_role: AgentRole)\n"
            "```python\n"
            "# Returns dependency: calls require_auth then checks role hierarchy\n"
            "# READ_ONLY < AGENT < SALES_MANAGER < ADMIN → 403 if insufficient\n"
            "```\n\n"
            "## JWT spec\n"
            "- Algorithm: **RS256** (NEVER HS256)\n"
            "- Claims: `sub` (agent_id), `role` (AgentRole), `exp`\n"
            "- Keys: `settings.JWT_PRIVATE_KEY`, `settings.JWT_PUBLIC_KEY` (PEM env vars)\n\n"
            "## Acceptance\n"
            "- Valid token → 200; expired → 401; wrong role → 403; inactive agent → 403\n\n"
            "**File:** `backend/src/core/security.py`\n"
            "_See_ `backend/instruction_dev4.md` § BLOCKING"
        ),
        labels=["P1-Blocker", "Dev4-FrontendAuth"],
        milestone="Foundation",
    ),

    Issue(
        title="[Dev4] Auth endpoints: POST /auth/login, /auth/refresh, GET /auth/me",
        body=(
            "**Owner:** Dev 4\n\n"
            "```\n"
            "POST /api/v1/auth/login    { email, password } → { access_token, token_type }\n"
            "POST /api/v1/auth/refresh  { access_token }    → { access_token, token_type }\n"
            "GET  /api/v1/auth/me                           → SalesAgent (require_auth)\n"
            "```\n\n"
            "## Acceptance\n"
            "- Login with correct credentials returns JWT verifiable by `require_auth`\n"
            "- `/me` returns agent details without hashed_password field"
        ),
        labels=["P1-Blocker", "Dev4-FrontendAuth"],
        milestone="Foundation",
    ),

    Issue(
        title="[Dev4] Lead CRUD: POST/GET/PATCH/DELETE /api/v1/leads",
        body=(
            "**Owner:** Dev 4\n"
            "**Depends on:** Dev 4 `require_auth` (self-dependency)\n\n"
            "```\n"
            "POST   /api/v1/leads              create (require_auth)\n"
            "GET    /api/v1/leads              list, filter status/agent, paginated\n"
            "GET    /api/v1/leads/{id}         detail\n"
            "PATCH  /api/v1/leads/{id}         update status / assignment\n"
            "DELETE /api/v1/leads/{id}         soft-delete: is_active=False (require_role: ADMIN)\n"
            "```\n\n"
            "Response must be paginated: `{ items, total, page, page_size }`\n\n"
            "**Files:** `src/api/v1/leads.py`, `src/application/dto/lead_dto.py`"
        ),
        labels=["P2-Core", "Dev4-FrontendAuth", "blocked"],
        milestone="Foundation",
    ),

    Issue(
        title="[Dev4] Fiverr webhook: create lead + publish NATS leads.created",
        body=(
            "**Owner:** Dev 4\n\n"
            "## POST /api/v1/integrations/fiverr/webhook\n"
            "1. Parse Fiverr webhook payload\n"
            "2. Create `LeadModel` in DB\n"
            "3. `await event_bus.publish('leads.created', 'lead.created.fiverr', {...})`\n"
            "4. Return 200\n\n"
            "**File:** `src/api/v1/integrations/`"
        ),
        labels=["P2-Core", "Dev4-FrontendAuth", "blocked"],
        milestone="Foundation",
    ),

    Issue(
        title="[Dev4] Next.js 15 frontend: 7 screens (dashboard, chat, quotation, resources, admin)",
        body=(
            "**Owner:** Dev 4\n"
            "**Depends on:** Dev 2 P1 API (suggestion panel), Dev 3 P2 API (quotation builder)\n\n"
            "## Screens\n"
            "| Screen | Route | Notes |\n"
            "|--------|-------|-------|\n"
            "| Login | `/login` | JWT → httpOnly cookie |\n"
            "| Dashboard | `/` | Lead pipeline Kanban, 4 columns |\n"
            "| Conversation | `/leads/[id]/chat` | Thread + input |\n"
            "| Suggestion panel | component | 5 cards, click-to-insert |\n"
            "| Quotation builder | `/leads/[id]/quotation` | Line items + send |\n"
            "| Resource library | `/resources` | Upload + list |\n"
            "| Admin | `/admin` | SALES_MANAGER/ADMIN only |\n\n"
            "## Hard constraints\n"
            "- TypeScript strict, no `any`\n"
            "- JWT in httpOnly cookie — NEVER localStorage\n"
            "- All API calls via `NEXT_PUBLIC_API_URL` env var — no hard-coded URLs\n\n"
            "**Directory:** `frontend/`"
        ),
        labels=["P2-Core", "Dev4-FrontendAuth", "blocked"],
        milestone="Production",
    ),

    Issue(
        title="[Dev4] CI workflow: ruff + mypy + pytest + prompt evals + frontend build",
        body=(
            "**Owner:** Dev 4\n\n"
            "## Steps (fail fast on first error)\n"
            "```yaml\n"
            "1. ruff check backend/src/\n"
            "2. mypy backend/src/ --ignore-missing-imports\n"
            "3. pytest backend/tests/ -x --tb=short\n"
            "4. pytest backend/prompts/ -k eval_suite   # P1 + P2\n"
            "5. npm run build   (frontend/)\n"
            "6. npm run lint    (frontend/)\n"
            "```\n\n"
            "**File:** `.github/workflows/ci.yml`"
        ),
        labels=["P3-Quality", "Dev4-FrontendAuth"],
        milestone="Production",
    ),

    Issue(
        title="[Dev4] CD workflow + K8s manifests: build → push → kubectl apply",
        body=(
            "**Owner:** Dev 4\n\n"
            "## CD (on merge to main)\n"
            "```yaml\n"
            "1. docker build -f deploy/docker/app.Dockerfile → push\n"
            "2. docker build -f deploy/docker/worker.Dockerfile → push\n"
            "3. kubectl apply -k deploy/k8s/\n"
            "4. kubectl rollout status deployment/betopia-api\n"
            "```\n\n"
            "## K8s scaling\n"
            "| Workload | Replicas | Autoscaler |\n"
            "|----------|----------|------------|\n"
            "| betopia-api | 4 | HPA CPU 70% max=20 |\n"
            "| worker p1-high | KEDA min=2 max=10 | Redis queue depth |\n"
            "| worker p2-normal | KEDA min=1 max=5 | Redis queue depth |\n"
            "| worker p3-batch | KEDA min=1 max=3 | Redis queue depth |\n\n"
            "## Acceptance\n"
            "- `kubectl apply --dry-run=client -k deploy/k8s/` exits 0\n\n"
            "**Files:** `.github/workflows/cd.yml`, `deploy/k8s/`"
        ),
        labels=["P3-Quality", "Dev4-FrontendAuth"],
        milestone="Production",
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def run(cmd: list[str], capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=capture, text=True)


def gh(*args: str, capture: bool = False) -> subprocess.CompletedProcess:
    return run(["gh", *args], capture=capture)


def check_gh_auth() -> bool:
    result = gh("auth", "status", capture=True)
    if result.returncode != 0:
        print("ERROR: Not authenticated with GitHub CLI.")
        print("Run:  gh auth login")
        return False
    return True


def get_milestone_number(title: str) -> str | None:
    """Return the milestone number for a given title, or None."""
    result = gh("api", "repos/{owner}/{repo}/milestones",
                "--jq", f'.[] | select(.title == "{title}") | .number',
                capture=True)
    num = result.stdout.strip()
    return num if num else None


# ─────────────────────────────────────────────────────────────────────────────
# Executors
# ─────────────────────────────────────────────────────────────────────────────

def create_labels(dry_run: bool) -> None:
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Creating {len(LABELS)} labels...")
    for name, color, desc in LABELS:
        if dry_run:
            print(f"  label: #{color} '{name}' — {desc}")
            continue
        result = gh("label", "create", name,
                    "--color", color,
                    "--description", desc,
                    "--force",     # update if already exists
                    capture=True)
        status = "ok" if result.returncode == 0 else f"WARN: {result.stderr.strip()}"
        print(f"  {name}: {status}")


def create_milestones(dry_run: bool) -> None:
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Creating {len(MILESTONES)} milestones...")
    for title, desc in MILESTONES:
        if dry_run:
            print(f"  milestone: '{title}' — {desc}")
            continue
        result = gh("api", "repos/{owner}/{repo}/milestones",
                    "--method", "POST",
                    "--field", f"title={title}",
                    "--field", f"description={desc}",
                    capture=True)
        if result.returncode == 0:
            print(f"  {title}: created")
        elif "already_exists" in result.stderr or "422" in result.stderr:
            print(f"  {title}: already exists (skipped)")
        else:
            print(f"  {title}: WARN — {result.stderr.strip()}")


def create_issues(dry_run: bool) -> None:
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Creating {len(ISSUES)} issues...")

    for issue in ISSUES:
        if dry_run:
            print(f"  [{', '.join(issue.labels)}] {issue.title}")
            continue

        cmd = [
            "gh", "issue", "create",
            "--title", issue.title,
            "--body", issue.body,
            "--label", ",".join(issue.labels),
        ]
        if issue.milestone:
            cmd += ["--milestone", issue.milestone]

        result = run(cmd, capture=True)
        if result.returncode == 0:
            url = result.stdout.strip()
            print(f"  created: {url}")
        else:
            print(f"  ERROR creating '{issue.title}': {result.stderr.strip()}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Set up GitHub labels, milestones and issues for the Sales Agent project."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be created without calling GitHub API")
    parser.add_argument("--labels-only", action="store_true",
                        help="Create labels and milestones only, skip issues")
    parser.add_argument("--issues-only", action="store_true",
                        help="Skip labels and milestones, create issues only")
    args = parser.parse_args()

    if not args.dry_run and not check_gh_auth():
        sys.exit(1)

    print("Sales Intelligence Agent v3.0 — GitHub board setup")
    print(f"Issues: {len(ISSUES)}  |  Labels: {len(LABELS)}  |  Milestones: {len(MILESTONES)}")

    if not args.issues_only:
        create_labels(dry_run=args.dry_run)
        create_milestones(dry_run=args.dry_run)

    if not args.labels_only:
        create_issues(dry_run=args.dry_run)

    print("\nDone.")


if __name__ == "__main__":
    main()
