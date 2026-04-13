# Sales Intelligence Agent — Project Context

> **Purpose of this file:** Complete development context. Load this in any Claude session on any machine to continue without re-explaining the project. Last updated: 2026-04-13.

---

## 1. What This Project Is

An AI-powered sales assistant for **Betopia**, a Fiverr software agency.

**The core workflow:**
1. A customer sends a message on Fiverr
2. The salesperson **manually pastes** that message into the web UI
3. The system generates **5 ranked reply suggestions** (P1 — Conversation Engine)
4. When requirements are clearer, the salesperson uploads documents (PDF/DOCX/etc.)
5. The system extracts structured requirements and generates a **proposal PDF** (P2 — Requirements Agent)

**Scale target:** 2,000 concurrent users, ~22 RPS peak, 99.9% uptime SLO, ~$30–60/day LLM cost.

---

## 2. Architecture: v3.0 (CURRENT — the only valid version)

> A 47-page PDF spec ("Sales Intelligence Agent Architecture v3.0 Final") was provided and supersedes everything. Do not reintroduce v1/v2 patterns.

### Three Pipelines
| Pipeline | Name | Trigger | Key output |
|---|---|---|---|
| P1 | Conversation Engine | Salesperson pastes customer message | 5 ranked reply suggestions |
| P2 | Requirements Agent | Salesperson uploads document | Structured requirements + proposal PDF |
| P3 | Data Layer | Async/batch | CDC, historical indexing, batch parsing |

### Tech Stack
| Concern | Technology |
|---|---|
| Language | Python 3.12+ |
| Web framework | FastAPI 0.115+ |
| Database | **PostgreSQL 17** (asyncpg, PgBouncer-aware pool) |
| Vector DB | **Qdrant 1.13+** (HNSW m=16, ef_construct=200, INT8 scalar quantisation) |
| Event bus | **NATS JetStream** (CloudEvents envelope, at-least-once) |
| Cache / broker | **Redis 7.4+** (suggestion cache 5 min, embedding cache 24 h, Celery broker) |
| Object storage | **MinIO** (S3-compatible, on VM3) |
| LLM primary | **GPT-4.1** (structured outputs, 5 suggestions, P2 extraction) |
| LLM fallback | **Claude Sonnet 4.6** (`claude-sonnet-4-6`) — triggers when GPT-4.1 >3 s |
| LLM tertiary | **vLLM in-house** (intent classification, tone validation, last resort) |
| Embeddings | **text-embedding-3-large** (3072 dimensions) — cached 24 h in Redis |
| Auth | **JWT RS256** (asymmetric, 1 h access / 7 d refresh) |
| RBAC | SALESPERSON, SALES_MANAGER, ADMIN, READ_ONLY |
| API Gateway | **Kong 3.9+** (DB-less mode, rate-limit 100 req/min/IP, CORS, request-size) |
| Workers | **Celery** (doc generation, conversation indexing, P1 suggestion pipeline) |
| Observability | Prometheus + Grafana + structlog |

### LLM Fallback Chain (P1)
```
GPT-4.1 ──(timeout >3s or error)──► Claude Sonnet 4.6 ──(error)──► vLLM
```
All 3 return the same structured output: 5 suggestions with rank, strategy, tone, preview_text, full_text, conversion_signal.

### Intent Classes (6)
`new_inquiry` | `follow_up` | `clarification` | `negotiation` | `angry` | `urgent`

### Suggestion Strategies (5)
`discovery` | `value_proposition` | `social_proof` | `urgency` | `negotiation`

---

## 3. Three-VM Production Topology

```
Internet ──► VM1:8000 (Kong, only public port)
                │
                └─► VM1:8080 (FastAPI, internal)
                        │
              ┌─────────┼─────────┐
              │         │         │
          VM1:5432   VM1:6379  VM1:4222
         (Postgres)  (Redis)   (NATS)
                        │
                    VM2: Celery workers
                    (connects to VM1 + VM3)
                        │
              ┌─────────┴─────────┐
           VM3:6333           VM3:9000
           (Qdrant)           (MinIO)
                           VM3:80 (Nginx proxy)
```

### Compose files
| File | Deploys to |
|---|---|
| `backend/docker-compose.vm1.yml` | Kong + FastAPI + PostgreSQL + Redis + NATS + Prometheus/Grafana |
| `backend/docker-compose.vm2.yml` | Celery worker + beat + Flower |
| `backend/docker-compose.vm3.yml` | Qdrant + MinIO + minio-init + Nginx |

### Cross-VM networking
- VM2 uses `extra_hosts` mapping `redis`, `postgres`, `nats` → `VM1_INTERNAL_IP`
- VM1/VM2 reach Qdrant/MinIO via `VM3_INTERNAL_IP` env var
- **OS firewall rules required** (not in compose files):
  - VM1: allow VM2 inbound on 5432, 6379, 4222
  - VM3: allow VM1+VM2 inbound on 6333, 9000, 80

### Deployment order
```bash
# 1. Generate RS256 keys (once, copy certs/ to all VMs)
cd backend && make certs

# 2. VM3 first (data layer)
cp .env.vm3.example .env   # fill QDRANT_API_KEY, MINIO_ROOT_USER/PASSWORD
make vm3-up

# 3. VM1
cp .env.vm1.example .env   # fill VM3_INTERNAL_IP + all secrets
make vm1-up

# 4. VM2
cp .env.vm2.example .env   # fill VM1_INTERNAL_IP + VM3_INTERNAL_IP
make vm2-up
```

---

## 4. Repository Structure

```
sales_agent_for_betopia/
└── backend/
    ├── src/
    │   ├── main.py                        # FastAPI app + lifespan (NATS + Qdrant init)
    │   ├── core/
    │   │   ├── settings.py                # All config via pydantic-settings
    │   │   ├── security.py                # RS256 JWT, Role enum, require_roles()
    │   │   ├── exceptions.py              # Domain exception hierarchy
    │   │   └── logging.py                 # structlog setup
    │   ├── domain/
    │   │   ├── entities/
    │   │   │   ├── lead.py                # + profile_id, score, intent_label
    │   │   │   ├── message.py             # + direction, intent_label, suggestion_selected_rank
    │   │   │   ├── conversation.py
    │   │   │   ├── sales_agent.py         # roles = SALESPERSON/SALES_MANAGER/ADMIN/READ_ONLY
    │   │   │   ├── quotation.py           # + proposal_id, UNDER_REVIEW status
    │   │   │   ├── suggestion.py          # NEW — Suggestion + SuggestionEvent
    │   │   │   ├── requirements_doc.py    # NEW — P2 extraction result
    │   │   │   ├── proposal.py            # NEW — PDF deliverable
    │   │   │   ├── fiverr_profile.py      # NEW — Fiverr profile (no webhook)
    │   │   │   └── resource.py
    │   │   ├── repositories/              # Abstract interfaces
    │   │   └── services/
    │   ├── application/
    │   │   ├── dto/                       # Pydantic request/response DTOs
    │   │   ├── ports/                     # Abstract interfaces (ILLMPort, IVectorStorePort)
    │   │   └── use_cases/                 # Business orchestration
    │   ├── infrastructure/
    │   │   ├── db/
    │   │   │   ├── session.py             # asyncpg, pool_size=40 (2000 users)
    │   │   │   ├── base.py                # SQLAlchemy declarative base
    │   │   │   ├── models/                # ⚠️ STILL MYSQL — needs PostgreSQL rewrite
    │   │   │   └── repositories/          # Concrete repository implementations
    │   │   └── clients/
    │   │       ├── llm_client.py          # GPT-4.1 → Claude → vLLM fallback chain
    │   │       ├── anthropic_client.py    # Claude Sonnet 4.6 tool_use (P1 fallback + P2 enrich)
    │   │       ├── vllm_client.py         # Intent classification + tone validation
    │   │       ├── qdrant_client.py       # Qdrant (HNSW, scalar quant, gRPC)
    │   │       ├── nats_client.py         # JetStream event bus
    │   │       ├── redis_cache_client.py  # Suggestion/embedding cache + rate limit
    │   │       ├── minio_client.py        # MinIO S3 object storage
    │   │       ├── document_generator.py  # .docx quotation generation
    │   │       ├── odoo_client.py         # Odoo ERP (future placeholder)
    │   │       ├── chromadb_client.py     # ❌ REPLACED — raises ImportError
    │   │       └── fiverr_client.py       # ❌ REMOVED — raises ImportError
    │   ├── api/
    │   │   └── v1/
    │   │       ├── router.py              # Aggregates all routers
    │   │       ├── input.py               # POST /input/message (P1 entry)
    │   │       ├── suggestions.py         # GET/POST /suggestions/*
    │   │       ├── requirements.py        # POST /requirements/upload (P2 entry)
    │   │       ├── proposals.py           # POST /proposals/generate + download
    │   │       ├── leads.py               # CRUD (no Fiverr webhook)
    │   │       ├── conversations.py
    │   │       ├── quotations.py
    │   │       ├── resources.py
    │   │       ├── replies.py             # ⚠️ DEPRECATED — use /input + /suggestions
    │   │       └── integrations/odoo.py
    │   └── workers/
    │       ├── celery_app.py
    │       ├── quotation_worker.py        # generate_quotation_doc task
    │       └── indexing_worker.py         # index_conversation task
    ├── prompts/
    │   ├── shared/
    │   │   ├── system_persona.yaml
    │   │   └── output_schemas/
    │   │       ├── suggestion_list_v1.json
    │   │       └── requirements_v1.json
    │   ├── p1_suggestion/
    │   │   ├── v1_suggestion_prompt.yaml
    │   │   ├── v1_tone_validator.yaml
    │   │   └── eval_suite.yaml
    │   ├── p2_extraction/
    │   │   ├── v1_extraction_prompt.yaml
    │   │   ├── v1_enrichment_prompt.yaml
    │   │   └── v1_budget_estimator.yaml
    │   └── p3_parsing/
    │       └── v1_data_parser.yaml
    ├── deploy/
    │   ├── docker/
    │   │   ├── app.Dockerfile             # FastAPI multi-stage, port 8080
    │   │   └── worker.Dockerfile          # Celery worker multi-stage
    │   ├── kong/
    │   │   └── kong.yml                   # Kong DB-less declarative config
    │   ├── nginx/
    │   │   └── nginx.conf                 # MinIO proxy + document download cache
    │   ├── postgres/
    │   │   └── init.sql                   # Logical replication, extensions
    │   └── qdrant/
    │       └── config.yaml                # HNSW + scalar quantisation config
    ├── certs/                             # RS256 key pair (gitignored, generate with make certs)
    ├── docker-compose.vm1.yml
    ├── docker-compose.vm2.yml
    ├── docker-compose.vm3.yml
    ├── docker-compose.server.yml          # Legacy single-VM dev only
    ├── .env.vm1.example
    ├── .env.vm2.example
    ├── .env.vm3.example
    ├── Makefile
    └── pyproject.toml
```

---

## 5. Key Settings Reference (`src/core/settings.py`)

```python
# PostgreSQL (asyncpg, PgBouncer-aware)
DATABASE_URL  = "postgresql+asyncpg://user:pass@host:port/db"
DATABASE_URL_SYNC = "postgresql+psycopg2://..."  # Alembic only

# Qdrant (3 collections, HNSW m=16, ef=200)
QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY
QDRANT_COLLECTION_CONVERSATIONS = "conversations"
QDRANT_COLLECTION_REQUIREMENTS  = "requirements"
QDRANT_COLLECTION_PRICING        = "pricing"

# LLM
LLM_PRIMARY_MODEL  = "gpt-4.1"
LLM_FALLBACK_MODEL = "claude-sonnet-4-6"
LLM_MINI_MODEL     = "gpt-4.1-mini"
EMBEDDING_MODEL    = "text-embedding-3-large"
EMBEDDING_DIMENSIONS = 3072
VLLM_BASE_URL      = "http://..."
LLM_PRIMARY_TIMEOUT  = 3.0   # seconds before Claude fallback kicks in
LLM_FALLBACK_TIMEOUT = 8.0

# NATS
NATS_URL = "nats://..."
NATS_STREAM_NAME = "sales_agent"
NATS_SUBJECT_PREFIX = "betopia.sales"

# Redis
REDIS_URL = "redis://:password@host:6379/0"
REDIS_SUGGESTION_CACHE_TTL = 300    # 5 min
REDIS_EMBEDDING_CACHE_TTL  = 86400  # 24 h

# MinIO
MINIO_ENDPOINT = "host:9000"   # no http:// prefix
MINIO_BUCKET_PROPOSALS    = "proposals"
MINIO_BUCKET_QUOTATIONS   = "quotations"
MINIO_BUCKET_REQUIREMENTS = "requirements"

# JWT RS256
JWT_RS256_PRIVATE_KEY_PATH = "./certs/private.pem"
JWT_RS256_PUBLIC_KEY_PATH  = "./certs/public.pem"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60
JWT_REFRESH_TOKEN_EXPIRE_DAYS   = 7

# P1
SUGGESTION_COUNT = 5
INTENT_CLASSES = ["new_inquiry","follow_up","clarification","negotiation","angry","urgent"]
```

---

## 6. RBAC (Role-Based Access Control)

```python
from src.core.security import Role, require_roles

class Role(StrEnum):
    SALESPERSON   = "SALESPERSON"    # paste messages, select suggestions
    SALES_MANAGER = "SALES_MANAGER"  # above + approve proposals, see all agents
    ADMIN         = "ADMIN"          # full access + user management
    READ_ONLY     = "READ_ONLY"      # dashboards only, no writes

# Usage on any FastAPI route:
@router.post("/...", dependencies=[Depends(require_roles(Role.SALESPERSON, Role.ADMIN))])
```

---

## 7. API Routes Reference

### P1 — Conversation Engine
```
POST /api/v1/input/message          → 202 Accepted + task_id  (P1 entry point)
GET  /api/v1/suggestions/{lead_id}  → poll for 5 suggestions
POST /api/v1/suggestions/{id}/select → record selection (A/B analytics)
POST /api/v1/suggestions/skip/{conv_id} → record manual typing
```

### P2 — Requirements Agent
```
POST /api/v1/requirements/upload    → 202 Accepted (file → MinIO → Celery extract)
GET  /api/v1/requirements/{id}      → extraction status + structured result
POST /api/v1/requirements/{id}/approve → SALES_MANAGER approve → triggers proposal
GET  /api/v1/requirements/lead/{id} → all docs for a lead

POST /api/v1/proposals/generate     → 202 Accepted (PDF generation queued)
GET  /api/v1/proposals/{id}         → status
GET  /api/v1/proposals/{id}/download → stream PDF
POST /api/v1/proposals/{id}/send    → mark as sent
GET  /api/v1/proposals/lead/{id}    → all proposals for a lead
```

### Core entities
```
POST/GET/PATCH/DELETE /api/v1/leads/*
GET/POST              /api/v1/conversations/*
GET/POST              /api/v1/quotations/*
POST/GET              /api/v1/resources/*
GET                   /health                  (no auth, used by Kong/LB)
GET                   /metrics                 (Prometheus, internal only)
```

### Deprecated
```
POST /api/v1/replies/suggest  → still works but deprecated; use /input + /suggestions
```

---

## 8. NATS Event Schema

All events follow CloudEvents 1.0 envelope:
```json
{
  "specversion": "1.0",
  "type": "betopia.sales.conversation.message_received",
  "source": "/sales-intelligence-agent",
  "id": "<uuid>",
  "time": "<iso8601>",
  "subject": "betopia.sales.conversation.message_received",
  "datacontenttype": "application/json",
  "data": { ... }
}
```

| Event type | Published by | Consumed by |
|---|---|---|
| `betopia.sales.conversation.message_received` | `/input/message` | P1 worker |
| `betopia.sales.conversation.suggestion_selected` | `/suggestions/{id}/select` | Analytics |
| `betopia.sales.requirements.extracted` | P2 worker | Enrichment worker |
| `betopia.sales.requirements.enriched` | Claude enrichment | Proposal generator |
| `betopia.sales.proposal.ready` | Proposal worker | Notification |

---

## 9. Qdrant Collections

| Collection | Content | Filter fields |
|---|---|---|
| `conversations` | Full conversation transcripts | lead_id, agent_id, status |
| `requirements` | Extracted requirements docs | lead_id, service_type, platform |
| `pricing` | Historical quotation line items | service_type, budget_range |

All collections: 3072-d vectors, HNSW m=16 ef_construct=200, INT8 scalar quantisation.

---

## 10. What Is DONE vs TODO

### ✅ Done

**Config layer**
- `pyproject.toml` — Python 3.12, asyncpg, qdrant-client, nats-py, pdfplumber, PyMuPDF, python-pptx, openpyxl, tenacity, reportlab, weasyprint, minio
- `src/core/settings.py` — full v3.0 settings (PostgreSQL, Qdrant, NATS, MinIO, RS256, LLM)
- `src/core/security.py` — RS256 JWT, Role enum, `require_roles()` FastAPI dependency
- `src/core/exceptions.py` — full exception hierarchy, no Fiverr exceptions

**Domain entities** (all correct v3.0)
- `lead.py`, `message.py`, `sales_agent.py`, `quotation.py` — updated
- `suggestion.py`, `requirements_doc.py`, `proposal.py`, `fiverr_profile.py` — new

**Infrastructure clients** (all wired up)
- `qdrant_client.py` — QdrantVectorClient (HNSW, gRPC, scalar quant, payload filters)
- `llm_client.py` — fallback chain GPT-4.1 → Claude → vLLM, 5 structured suggestions
- `anthropic_client.py` — Claude Sonnet 4.6 tool_use (P1 fallback + P2 enrichment)
- `vllm_client.py` — intent classification, tone validation, last-resort suggestions
- `nats_client.py` — JetStream, CloudEvents, convenience emit_* methods
- `redis_cache_client.py` — SHA256 cache keys, suggestion/embedding/rate-limit
- `minio_client.py` — upload, download, presign_download, delete

**API routes** — all scaffolded with RBAC
- `input.py`, `suggestions.py`, `requirements.py`, `proposals.py` (new)
- `leads.py` (Fiverr webhook removed, RBAC added)
- `replies.py` (marked deprecated, uses Qdrant)

**Prompts (Prompt-as-Code)**
- P1: `v1_suggestion_prompt.yaml`, `v1_tone_validator.yaml`, `eval_suite.yaml`
- P2: `v1_extraction_prompt.yaml`, `v1_enrichment_prompt.yaml`, `v1_budget_estimator.yaml`
- P3: `v1_data_parser.yaml`
- Shared: `system_persona.yaml`, `suggestion_list_v1.json`, `requirements_v1.json`

**DevOps**
- `docker-compose.vm1.yml`, `docker-compose.vm2.yml`, `docker-compose.vm3.yml`
- `deploy/docker/app.Dockerfile`, `deploy/docker/worker.Dockerfile`
- `deploy/kong/kong.yml` — DB-less, rate-limit, CORS, request-size, correlation-ID
- `deploy/nginx/nginx.conf` — MinIO proxy cache, bucket routes
- `deploy/qdrant/config.yaml`, `deploy/postgres/init.sql`
- `.env.vm1.example`, `.env.vm2.example`, `.env.vm3.example`
- `Makefile` — vm1/vm2/vm3 up/down/logs/build targets, certs, diagnostics
- `src/main.py` — NATS + Qdrant lifespan, all exception handlers, `/health` endpoint

---

### ❌ Not Done (priority order)

#### Priority 1 — App won't start without these

**1. Rewrite SQLAlchemy ORM models** (`src/infrastructure/db/models/`)
- ALL models still use `sqlalchemy.dialects.mysql.CHAR` and `JSON`
- Must change to: native PostgreSQL `UUID` type, `JSONB`, `sa.Text`
- Add new models: `SuggestionModel`, `RequirementsDocModel`, `ProposalModel`
- Messages table: add `direction`, `intent_label`, `suggestion_selected_rank`, `sent_at`
- Leads table: add `profile_id`, `score`, `intent_label`, `erp_record_id`

**2. Alembic migrations** — delete all existing migrations, create fresh PostgreSQL migration
```bash
alembic revision --autogenerate -m "v3_initial_postgresql_schema"
```

**3. Update `IVectorStorePort`** (`src/application/ports/vector_store_port.py`)
- Current signature: `upsert(collection, doc_id, text, metadata)` — no vector arg
- Qdrant needs: `upsert(collection, doc_id, text, metadata, vector: list[float])`
- Add `query_similar(collection, query_vector: list[float], ...)` (vector not text)

#### Priority 2 — Core pipeline not functional yet

**4. New DB repositories**
- `RequirementsDocRepositoryImpl` — CRUD for requirements_doc
- `ProposalRepositoryImpl` — CRUD for proposals
- `SuggestionRepositoryImpl` — CRUD for suggestions + SuggestionEvents

**5. P1 Celery worker** (`src/workers/p1_suggestion_worker.py`)
```python
@celery_app.task(name="generate_p1_suggestions")
def generate_p1_suggestions(message_id, conversation_id, lead_id):
    # 1. classify_intent (vllm)
    # 2. embed_text (openai, check redis cache first)
    # 3. qdrant.query_similar(conversations) + query_similar(pricing)
    # 4. llm_client.generate_suggestions (fallback chain)
    # 5. validate_tone for each suggestion (vllm)
    # 6. store in DB + redis cache
    # 7. emit NATS (for WebSocket push)
```

**6. P2 Celery worker** (`src/workers/p2_extraction_worker.py`)
```python
@celery_app.task(name="extract_requirements")
def extract_requirements(doc_id, file_path, mime_type):
    # 1. parse file based on mime_type (pdfplumber/pymupdf/docx/pptx/openpyxl/whisper/vision)
    # 2. gpt-4.1 extraction → RequirementsDoc
    # 3. anthropic enrichment (budget estimate, stack, risk flags, lead score)
    # 4. embed and upsert to qdrant requirements collection
    # 5. update DB + emit NATS betopia.sales.requirements.enriched
```

**7. WebSocket endpoint** (`src/api/v1/ws.py`)
```python
@router.websocket("/ws/suggestions/{lead_id}")
async def ws_suggestions(websocket, lead_id, ...):
    # Subscribe to NATS betopia.sales.conversation.suggestion_selected
    # Push suggestions to connected salesperson
```

#### Priority 3 — Quality & correctness

**8. Rewrite use cases** to v3.0 patterns
- `SuggestRepliesUseCase` — still uses old ChromaDB-style `query_text` signature
- `GenerateQuotationUseCase` — needs MinIO integration for doc storage
- New: `ProcessMessageUseCase` (P1), `ExtractRequirementsUseCase` (P2), `GenerateProposalUseCase`

**9. Update indexing worker** (`src/workers/indexing_worker.py`)
- Currently uses `ChromaDBClient` — replace with `QdrantVectorClient`
- Must embed text first (llm_client.embed_text), then upsert with vector

**10. Update quotation worker** (`src/workers/quotation_worker.py`)
- Store generated `.docx` in MinIO instead of local disk
- Use `MinIOStorageClient.upload_file(bucket_quotations, ...)`

---

## 11. Patterns to Follow

### Adding a new API endpoint
```python
# 1. Define route with RBAC
@router.post("/...", dependencies=[Depends(require_roles(Role.SALESPERSON, Role.ADMIN))])
async def endpoint(dto: MyDTO, db: AsyncSession = Depends(get_db)) -> ResponseDTO:
    ...

# 2. Publish to NATS for async side-effects
await nats_client.publish(event_type="betopia.sales.x.y", subject_suffix="x.y", data={...})

# 3. Check Redis cache before expensive LLM calls
cached = await cache.get_suggestions(conversation_id, message)
if cached: return cached
```

### Adding a Celery task
```python
@celery_app.task(name="task_name", bind=True, max_retries=3)
def task_name(self, arg: str) -> None:
    async def _run() -> None:
        async with AsyncSessionLocal() as session:
            ...
    try:
        asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
```

### Using the LLM fallback chain
```python
# Always go through LLMClient — it handles the chain internally
client = LLMClient()
suggestions = await client.generate_suggestions(
    customer_message=..., intent_label=..., recent_messages=...,
    similar_conversations=..., resources_context=...
)
```

### Using Qdrant
```python
# Always embed first, then upsert
vector = await cache.get_embedding(text) or await llm.embed_text(text)
await cache.set_embedding(text, vector)  # cache 24h
await qdrant.upsert(collection, doc_id, text, metadata, vector=vector)

# Query
results = await qdrant.query_similar(
    collection, query_vector=vector, n_results=5,
    filters={"lead_id": str(lead_id)}
)
```

### Storing documents
```python
minio = MinIOStorageClient()
path = minio.upload_bytes(settings.MINIO_BUCKET_PROPOSALS, f"{proposal_id}.pdf", pdf_bytes, "application/pdf")
url = minio.presign_download(settings.MINIO_BUCKET_PROPOSALS, f"{proposal_id}.pdf")
```

---

## 12. Absolute Rules (Never Break)

1. **No Fiverr webhook.** There is zero Fiverr API connection. `fiverr_client.py` raises ImportError intentionally. Salesperson always pastes manually.
2. **No MySQL.** `aiomysql`, `pymysql`, `CHAR(36)` are banned. Use `asyncpg` + native PostgreSQL `UUID`.
3. **No ChromaDB.** `chromadb_client.py` raises ImportError. Use `qdrant_client.py`.
4. **No HS256.** JWT is always RS256 asymmetric. Private key signs, public key verifies.
5. **No direct disk storage for documents.** All generated PDFs/DOCX go to MinIO on VM3.
6. **Always 5 suggestions** — not 3, not 4. `SUGGESTION_COUNT = 5`.
7. **Kong is the only public port.** FastAPI is on :8080 internal only.
8. **LLM calls always go through the fallback chain** — never call OpenAI directly in business logic. Use `LLMClient`.

---

## 13. Dev Environment Setup (any machine)

```bash
# Prerequisites: Python 3.12, Docker, openssl

git clone <repo>
cd sales_agent_for_betopia/backend

# Python environment
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Generate JWT keys
make certs

# Copy env and fill in secrets
cp .env.vm1.example .env
# Edit .env: set OPENAI_API_KEY, ANTHROPIC_API_KEY, POSTGRES_PASSWORD, etc.

# For local dev (single VM, no Kong):
docker compose -f docker-compose.server.yml up -d   # postgres + qdrant + nats + redis
uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload

# Run Alembic migrations
make migrate

# For production (three VMs):
# → See Section 3 deployment order above
make vm3-up   # on VM3
make vm1-up   # on VM1
make vm2-up   # on VM2
```

---

## 14. Makefile Quick Reference

```bash
make dev              # uvicorn reload on :8080
make worker           # celery worker
make migrate          # alembic upgrade head
make migrate-new msg="description"
make certs            # generate RS256 key pair

make vm1-up/down/logs/build
make vm2-up/down/logs/build
make vm3-up/down/logs/build

make lint             # ruff + mypy
make format           # ruff format + autofix
make test             # pytest with coverage
make test-evals       # P1/P2 prompt evaluation suite

make kong-status      # health check through Kong
make qdrant-status    # list Qdrant collections
make nats-status      # JetStream stream info
make minio-status     # MinIO health
make db-backup        # pg_dump → gzipped SQL

make certs            # openssl RS256 keygen → ./certs/
```

---

## 15. File Locations for Next Tasks

When implementing the next priorities, these are the exact files to edit or create:

| Task | File |
|---|---|
| ORM models rewrite | `src/infrastructure/db/models/lead_model.py` etc. |
| Add new ORM models | `src/infrastructure/db/models/suggestion_model.py` (new) |
| Fix IVectorStorePort | `src/application/ports/vector_store_port.py` |
| Fresh Alembic migration | `alembic/versions/` (delete old, create new) |
| P1 suggestion worker | `src/workers/p1_suggestion_worker.py` (new) |
| P2 extraction worker | `src/workers/p2_extraction_worker.py` (new) |
| WebSocket suggestions | `src/api/v1/ws.py` (new) |
| Fix indexing worker | `src/workers/indexing_worker.py` (replace ChromaDB) |
| Fix quotation worker | `src/workers/quotation_worker.py` (add MinIO) |
| P1 use case | `src/application/use_cases/process_message.py` (new) |
| P2 use case | `src/application/use_cases/extract_requirements.py` (new) |
| New repositories | `src/infrastructure/db/repositories/*_repository_impl.py` |
