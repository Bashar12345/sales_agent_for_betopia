# Team Split — Sales Intelligence Agent v3.0
## 4 Parallel Workstreams

> Each developer works on an independent vertical. The only hard dependencies are the
> **shared contracts** listed in each section — agree on those on Day 1 and then work in parallel.

---

## Dev 1 — Data Foundation (P3 + Infrastructure)

**Owns:** PostgreSQL schema, Qdrant collections, Redis, NATS event bus, Debezium CDC,
embedding pipeline, Docker Compose, DB migrations, health endpoints.

### Files to implement

```
backend/src/infrastructure/db/
    base.py                              # SQLAlchemy async engine setup
    session.py                           # AsyncSession factory + dependency
    models/lead_model.py                 # leads table (all 9 core tables)
    models/conversation_model.py         # messages, suggestion_events, conversation_feedback
    models/quotation_model.py            # requirements_docs, proposals, quotation_templates
    models/resource_model.py             # vector_index_log, event_outbox
    models/sales_agent_model.py          # fiverr_profiles, users, rbac
    models/mixins.py                     # TimestampMixin, UUIDMixin
    repositories/lead_repository_impl.py
    repositories/conversation_repository_impl.py
    repositories/quotation_repository_impl.py
    repositories/resource_repository_impl.py
    migrations/                          # Alembic migration files for all 9 tables

backend/src/infrastructure/clients/
    qdrant_client.py                     # QdrantVectorStore — upsert, search, delete, health
    redis_cache_client.py                # RedisCache — get/set/invalidate + rate-limit buckets
    nats_client.py                       # NATSEventBus — publish CloudEvents, subscribe

backend/src/workers/
    indexing_worker.py                   # Celery tasks: embed_and_upsert, re_embed_collection
    celery_app.py                        # Celery config + priority queues (P1-HIGH, P2-NORMAL, P3-BATCH)

backend/src/api/v1/
    health.py                            # GET /health  GET /health/ready

backend/deploy/
    docker-compose.yml                   # postgres17, redis7.4, qdrant1.13, nats2.10
    postgres/init.sql                    # all 9 tables + indexes + partitioning
    qdrant/config.yaml                   # 3 collections: conversation, requirements, pricing
    nginx/{backend.conf}

backend/src/core/
    settings.py                          # Pydantic Settings for all env vars
    exceptions.py                        # Domain + infra exception hierarchy
    logging.py                           # structlog JSON setup + OpenTelemetry
```

### What you build

| Component | Spec Reference | Key Detail |
|---|---|---|
| PostgreSQL 17 schema | §5.3 | All 9 tables, monthly partitioning on leads/messages, GIN on JSONB, composite indexes |
| Qdrant 3 collections | §5.1 | Conversation (HNSW ef=128 m=16 scalar-quant), Requirements (ef=128), Pricing (ef=64 m=8) |
| Embedding service | §P3-05 | text-embedding-3-large, batch=100, Redis cache 24h TTL, exponential backoff on 429 |
| NATS event bus | §2.1 L7 | CloudEvents spec, at-least-once, publish: suggestion.generated, feedback.recorded, etc. |
| Transactional outbox | §5.3 | event_outbox table + Debezium CDC → NATS |
| Redis cluster | §L4 | Suggestion cache 5min TTL, embedding cache 24h, rate-limit token buckets |
| Celery workers | §L4 | Priority queues: P1-HIGH, P2-NORMAL, P3-BATCH; DLQ for failures |
| Health endpoints | §10.1 | `/health` (liveness) + `/health/ready` (checks redis/qdrant/postgres) |

### Contracts you publish to the team (Day 1 — agree before coding)

```python
# src/application/ports/vector_store_port.py  — DEV 1 writes this interface
class VectorStorePort(Protocol):
    async def upsert(self, collection: str, points: list[VectorPoint]) -> None: ...
    async def search(self, collection: str, vector: list[float],
                     k: int, filters: dict) -> list[SearchResult]: ...
    async def delete(self, collection: str, ids: list[UUID]) -> None: ...

# src/application/ports/llm_port.py  — DEV 1 writes the interface; Dev 2/3 implement it
class EmbeddingPort(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

# src/application/ports/event_bus_port.py  — NEW, DEV 1 writes
class EventBusPort(Protocol):
    async def publish(self, event_type: str, payload: dict) -> None: ...
```

### Dependencies you need from others

- **None.** This workstream has no upstream code dependencies. Start on Day 1.

### Delivers to team by Day 3

- `docker-compose.yml` running (postgres + redis + qdrant + nats reachable locally)
- `VectorStorePort`, `EmbeddingPort`, `EventBusPort` interfaces committed to `main`
- Alembic migrations runnable with `alembic upgrade head`
- `GET /health/ready` returns 200

---

## Dev 2 — P1: Conversation Suggestion Engine

**Owns:** Intent classification (vLLM), embedding lookup, Qdrant conversation search,
GPT-4.1 suggestion ranking, tone validation, WebSocket/SSE delivery, Redis suggestion
cache, feedback loop, Celery LLM workers.

### Files to implement

```
backend/src/
    api/v1/
        input.py           # POST /api/v1/input/message
        suggestions.py     # GET /{lead_id}, POST /{id}/select, GET /{user_id}/stream (SSE)
        conversations.py   # GET /leads/{id}/history  +  WS /ws/suggestions/{user_id}

    application/
        use_cases/suggest_replies.py     # orchestrates P1-01 → P1-11
        dto/reply_dto.py                 # SuggestionRequest, SuggestionResponse, FeedbackRequest

    domain/
        services/reply_service.py        # pure domain logic: rank, filter, format
        entities/suggestion.py           # Suggestion dataclass
        entities/message.py              # Message dataclass

    infrastructure/
        clients/llm_client.py            # OpenAI GPT-4.1 structured outputs
        clients/vllm_client.py           # vLLM intent classifier + tone validator
        clients/anthropic_client.py      # Claude Sonnet 4.6 (fallback)

    workers/
        suggestion_worker.py             # Celery task: run_p1_pipeline(message_id)

backend/prompts/p1_suggestion/
    v1_suggestion_prompt.yaml            # system prompt + user template
    v1_tone_validator.yaml
    eval_suite.yaml                      # 50+ test cases

backend/prompts/shared/
    output_schemas/suggestion_list_v1.json   # structured output JSON schema
    system_persona.yaml
```

### What you build

| Step | Component | Spec | Latency target |
|---|---|---|---|
| P1-01 | Manual paste handler | POST /api/v1/input/message — JWT + idempotency key | <50ms |
| P1-02 | Intent classifier | vLLM: new_inquiry / follow_up / clarification / negotiation / angry / urgent | <200ms |
| P1-03 | Embedding service | text-embedding-3-large via EmbeddingPort, Redis cache 24h | <200ms (<5ms cached) |
| P1-04 | Conversation DB search | Qdrant cosine k=20 filtered by intent_label + profile_id | <100ms |
| P1-05 | Chat history loader | Last 10 messages for lead_id from PostgreSQL read replica | <50ms |
| P1-06 | Context assembler | system_prompt + history + top-20 matches + message + intent + style_guide | <10ms |
| P1-07 | LLM ranking agent | GPT-4.1 structured output → exactly 5 SuggestionSchema objects | <3,000ms |
| P1-08 | Tone validator | vLLM: professional tone check, auto-reject pushy patterns, retry once | <150ms |
| P1-09 | Suggestion formatter | max 400 chars, no markdown, Fiverr-safe chars, rank badges | <20ms |
| P1-10 | Cache + deliver | Redis SHA256(embedding) key → push via WebSocket/SSE → publish NATS event | <30ms |
| P1-11 | Selection feedback | log selection, publish feedback.recorded, async update Qdrant payload | <50ms async |

### Structured output schema (implement exactly)

```json
{
  "suggestions": [
    {
      "rank": 1,
      "strategy": "social_proof | value_lead | discovery | quick_quote | portfolio",
      "preview": "<first 80 chars>",
      "full_text": "<max 400 chars>",
      "tone": "friendly | confident | direct | consultative",
      "conversion_signal": "high | medium | low"
    }
  ]
}
```

### LLM fallback chain

```
GPT-4.1  --timeout 3s-->  Claude Sonnet 4.6  --timeout 3s-->  vLLM in-house
```
Use Tenacity circuit breaker per provider. All calls must be `async def`.

### Dependencies you need from others

| Need | From | Available by |
|---|---|---|
| `VectorStorePort` interface | Dev 1 | Day 1 |
| `EmbeddingPort` interface | Dev 1 | Day 1 |
| `EventBusPort` interface | Dev 1 | Day 1 |
| `docker-compose.yml` (redis + qdrant running) | Dev 1 | Day 3 |
| JWT auth middleware | Dev 4 | Day 2 |

### Contracts you publish to team

```python
# Celery task signature — Dev 3 & Dev 4 can enqueue P1 tasks
run_p1_pipeline.apply_async(
    args=[message_id],
    queue="p1-high",
    priority=9
)
```

### Delivers by Day 5

- `POST /api/v1/input/message` returns 202 + task_id
- Celery worker processes P1 pipeline end-to-end
- WebSocket push working in local dev
- Suggestions visible in browser (basic UI from Dev 4)

---

## Dev 3 — P2: Requirements Engineering Agent

**Owns:** File ingestion (PDF/DOCX/PPTX/images/audio/email/XLS), text extraction,
GPT-4.1 extraction with structured outputs, gap detection, Claude Sonnet 4.6 RAG
enrichment with tool_use, pricing DB lookup, budget/timeline estimation, resource
matching, requirements doc renderer, proposal generation, human review gate.

### Files to implement

```
backend/src/
    api/v1/
        requirements.py    # POST /ingest, GET /{lead_id}, PATCH /{id}, POST /{id}/approve, GET /{id}/gaps
        proposals.py       # POST /proposals, GET /{id}/pdf, PATCH /{id}, POST /{id}/approve
        quotations.py      # pricing + quotation template endpoints
        resources.py       # developer resource matching

    application/
        use_cases/process_fiverr_lead.py     # P2-01 → P2-12 orchestration
        use_cases/generate_quotation.py      # budget + timeline estimation
        use_cases/upload_resource.py         # file upload + virus scan + S3
        dto/quotation_dto.py                 # RequirementsRequest, RequirementsResponse
        dto/resource_dto.py                  # ResourceUpload, ResourceResponse
        ports/document_generator_port.py     # PDF renderer port

    domain/
        services/quotation_service.py        # gap detection, confidence scoring
        entities/requirements_doc.py         # RequirementsDoc dataclass
        entities/proposal.py                 # Proposal dataclass
        entities/quotation.py                # Quotation, BudgetEstimate dataclasses
        repositories/quotation_repository.py # interface

    infrastructure/
        clients/
            document_generator.py            # WeasyPrint + ReportLab PDF renderer
        db/
            repositories/quotation_repository_impl.py

    workers/
        quotation_worker.py                  # Celery tasks: extract_requirements, enrich_requirements

backend/prompts/p2_extraction/
    v1_extraction_prompt.yaml       # GPT-4.1 RequirementsSchema structured output
    v1_enrichment_prompt.yaml       # Claude Sonnet 4.6 tool_use enrichment
    v1_budget_estimator.yaml        # GPT-4.1 BudgetEstimateSchema
    eval_suite.yaml

backend/prompts/shared/
    output_schemas/requirements_v1.json
    output_schemas/budget_estimate_v1.json
```

### What you build

| Step | Component | Spec | Notes |
|---|---|---|---|
| P2-01 | File ingestion API | POST /api/v1/requirements/ingest — MIME + magic bytes + ClamAV scan + S3 | Max 50MB/file |
| P2-02 | Parallel file processor | Celery task group — each file type to specialist extractor + Whisper for audio | Concurrent |
| P2-03 | Text cleaner | Strip HTML, normalize whitespace, dedup paragraphs, langdetect, DeepL if non-EN | |
| P2-04 | Extraction agent | GPT-4.1 structured output → RequirementsSchema (service_type, platform, features[], budget_range, deadline, tech_preferences, client_notes[], extraction_confidence) | |
| P2-05 | Gap detector | Validate required fields; generate clarifying question per missing field | |
| P2-06 | Requirements DB embedding | Embed JSON summary, Qdrant Requirements collection k=10 | |
| P2-07 | Enrichment agent | Claude Sonnet 4.6 tool_use: search_similar_projects / get_pricing_data / validate_tech_stack — mark EXTRACTED / INFERRED / MISSING | 200K context |
| P2-08 | Pricing DB lookup | Embed service_type+features+tech_stack, Qdrant Pricing k=5, retrieve agreed_price/delivery_days | |
| P2-09 | Budget & timeline estimator | GPT-4.1 → price_min/max/recommended, timeline_days, milestone_breakdown[], confidence_score | flag <0.7 |
| P2-10 | Resource matching | Match against internal developer DB — experience, availability, team composition | |
| P2-11 | Requirements doc renderer | HTML/JSON → Executive Summary, Feature List, Tech Stack, Budget, Timeline, Flagged Questions | |
| P2-12 | Human review gate | Editable UI (Dev 4 builds UI), APPROVAL/REVISION, diff log, publish requirement.approved | |

### RequirementsSchema (implement exactly)

```python
class RequirementsSchema(BaseModel):
    service_type: str
    platform: list[str]
    features: list[FeatureItem]          # {name, priority, description}
    budget_range: BudgetRange            # {min, max, currency, source}
    deadline: DeadlineEstimate           # {days, confidence}
    tech_preferences: list[str]
    client_notes: list[str]
    missing_fields: list[MissingField]   # {field, clarifying_question}
    extraction_confidence: float         # 0.0–1.0
```

### File type → extractor mapping

| Input | Library | Notes |
|---|---|---|
| PNG / JPG screenshot | GPT-4.1 Vision (native) | Multimodal, no extra lib |
| PDF (text) | pdfplumber | |
| PDF (scanned) | PyMuPDF + GPT-4.1 Vision | fallback |
| DOCX | python-docx 1.1+ | |
| PPTX | python-pptx 0.6+ | |
| Meeting transcript (txt) | Direct NLP segmentation | |
| Audio recording | OpenAI Whisper large-v3 | batch via API |
| Email thread | python-email stdlib | MSG/EML reconstruction |
| XLS / XLSX | openpyxl 3.1+ | |

### Dependencies you need from others

| Need | From | Available by |
|---|---|---|
| `VectorStorePort` interface | Dev 1 | Day 1 |
| `EmbeddingPort` interface | Dev 1 | Day 1 |
| `EventBusPort` interface | Dev 1 | Day 1 |
| `docker-compose.yml` running | Dev 1 | Day 3 |
| JWT auth middleware | Dev 4 | Day 2 |
| `anthropic_client.py` (Claude Sonnet 4.6) | Dev 2 | Day 4 |

### Delivers by Day 8

- `POST /api/v1/requirements/ingest` processes all file types
- Requirements doc generated end-to-end for a sample brief
- Budget estimate with confidence score produced
- Proposal PDF rendered from template

---

## Dev 4 — Frontend + Auth + Admin + Observability + DevOps

**Owns:** Next.js 15 Sales UI, JWT auth (RS256), WebSocket/SSE client, suggestion
display, requirements editor, admin dashboard, Vector DB management portal,
operations monitoring dashboard, Kubernetes manifests, CI/CD, Prometheus/Grafana,
OpenTelemetry, feature flags.

### Files to implement

```
frontend/                                    # NEW — create this directory
    app/
        (auth)/login/page.tsx
        (dashboard)/
            leads/page.tsx                   # lead list + search
            leads/[id]/page.tsx              # conversation view + paste input
            leads/[id]/suggestions/page.tsx  # P1 suggestion cards
            leads/[id]/requirements/page.tsx # P2 requirements editor
            leads/[id]/proposal/page.tsx     # proposal preview + approve
        admin/
            dashboard/page.tsx               # system health + AI metrics
            vectordb/page.tsx                # Vector DB management portal
            review-queue/page.tsx            # admin review queue
            token-usage/page.tsx             # LLM cost tracker
        layout.tsx
        providers.tsx                        # QueryClient + WebSocket context
    components/
        SuggestionCard.tsx
        SuggestionList.tsx
        RequirementsEditor.tsx
        FileUploadZone.tsx
        ConversationThread.tsx
        HealthTrafficLight.tsx
        CostGauge.tsx
    lib/
        api.ts                               # typed API client (all endpoints)
        websocket.ts                         # WS + SSE connection manager with reconnect
        auth.ts                              # JWT storage, refresh, interceptor
    next.config.ts
    tailwind.config.ts
    package.json

backend/src/
    core/
        security.py                          # JWT RS256 sign/verify, RBAC decorator, rate limit
    api/v1/
        auth.py                              # POST /auth/login, POST /auth/refresh
        leads.py                             # GET /leads, POST /leads, GET /leads/{id}
        replies.py                           # feedback endpoints
        admin/
            metrics.py                       # GET /admin/metrics, /admin/token-usage
            feature_flags.py                 # POST /admin/feature-flags/{flag}
            review_queue.py                  # GET+POST /admin/review-queue/*
            audit_log.py                     # GET /admin/audit-log
            vectordb.py                      # full CRUD on all 3 Qdrant collections
        dashboard.py                         # GET /dashboard/health, /dashboard/metrics/*
    application/
        dto/lead_dto.py
        dto/conversation_dto.py

backend/observability/
    prometheus/prometheus.yml                # scrape configs for all services
    grafana/
        dashboards/
            executive.json
            engineering.json
            ai_performance.json
            slo.json
        provisioning/

backend/deploy/
    k8s/
        deployment.yaml                      # P1, P2, P3, frontend deployments
        hpa.yaml                             # HPA for all services
        keda-scaledobjects.yaml              # KEDA queue-depth scaling
        ingress.yaml                         # Kong ingress
        namespace.yaml
        secret.example.yaml
    docker/
        app.Dockerfile
        worker.Dockerfile
    .github/workflows/
        ci.yml                               # lint + type-check + test + prompt-eval
        cd.yml                               # build + push + deploy on merge to main
```

### What you build

**Auth system (Day 1–2, other devs depend on this)**
- JWT RS256 middleware for FastAPI — all protected routes
- RBAC: `SALESPERSON | SALES_MANAGER | ADMIN | READ_ONLY`
- Rate limiting: Redis token bucket (100/min salesperson, 500/min manager, 1000/min admin)
- `POST /auth/login` and `POST /auth/refresh`

**Sales UI (Day 1–5)**
- Next.js 15 app with Tailwind 4.x
- Paste area → fires `POST /api/v1/input/message` → polls task_id → receives suggestions via WebSocket/SSE
- SuggestionCard components (rank badge, strategy label, copy button, select button)
- File upload zone for P2 (drag-and-drop, progress bar, multi-file)
- Requirements editor (inline editable fields, approve/revise buttons, diff display)
- Proposal preview + approve gate

**Admin & Vector DB Portal (Day 5–10)**
- System health panel: traffic-light per service (§15.2)
- AI performance panel: selection rates, prompt A/B results, LLM latency (§15.3)
- LLM cost dashboard: daily spend gauge, cost-by-model pie, monthly projection (§15.4)
- Vector DB portal: CRUD on all 3 Qdrant collections, bulk import/export, similarity search tester (§16)
- Admin review queue: approve/reject pending records with side-by-side similarity view

**Observability (Day 3–5)**
- Prometheus scrape configs for all FastAPI services + Redis + Qdrant + NATS
- 4 Grafana dashboards: Executive, Engineering, AI Performance, SLO
- OpenTelemetry auto-instrumentation on all FastAPI apps
- Sentry integration (all services)

**DevOps (Day 1–3, shared with Dev 1)**
- K8s manifests for all services
- KEDA ScaledObjects for P1/P2/P3 workers
- GitHub Actions CI: `ruff` lint + `mypy` + `pytest` + prompt eval suite
- GitHub Actions CD: build Docker images → push → rolling deploy

### JWT contract — publish on Day 1

```python
# backend/src/core/security.py
# Every other dev imports this to protect their routes:

from src.core.security import require_auth, require_role, RBACRole

@router.post("/api/v1/input/message")
async def submit_message(
    payload: MessageRequest,
    current_user: User = Depends(require_auth),
):
    ...

@router.get("/api/v1/admin/metrics")
async def get_metrics(
    current_user: User = Depends(require_role(RBACRole.ADMIN)),
):
    ...
```

### Dependencies you need from others

| Need | From | Available by |
|---|---|---|
| `docker-compose.yml` (postgres running) | Dev 1 | Day 3 |
| `POST /api/v1/input/message` working | Dev 2 | Day 5 |
| `POST /api/v1/requirements/ingest` working | Dev 3 | Day 5 |

### Delivers to team by Day 2 (hard dependency)

- `require_auth` / `require_role` FastAPI dependencies committed to `main`
- `docker-compose.yml` has `frontend` service stub
- Basic Next.js app running at `localhost:3000`

---

## Shared Contracts — Agree on Day 1

These are the interfaces all 4 devs share. Dev 1 writes the interfaces; all others implement or consume them.

### Event types (NATS)

```
suggestion.generated     { message_id, lead_id, suggestions[], latency_ms, prompt_version }
feedback.recorded        { message_id, suggestion_rank, lead_id, was_selected }
requirement.extracted    { lead_id, req_doc_id, confidence, missing_fields[] }
requirement.approved     { lead_id, req_doc_id, approved_by }
data.indexed             { collection, qdrant_point_id, source_table, source_id }
data.validation_failed   { record_id, reason }
file.uploaded            { lead_id, s3_uri, mime_type, size_bytes }
```

### Branch strategy

```
main              ← protected, deploys to staging
feature/dev1-*    ← Dev 1 branches
feature/dev2-*    ← Dev 2 branches
feature/dev3-*    ← Dev 3 branches
feature/dev4-*    ← Dev 4 branches
```

PR into `main` requires: CI green + 1 review from any other dev.

### Env vars (all devs use same `.env.example`)

```
# DB
POSTGRES_URL=postgresql+asyncpg://user:pass@localhost:5432/salesagent
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333
NATS_URL=nats://localhost:4222

# AI
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
VLLM_URL=http://localhost:8000

# Auth
JWT_PRIVATE_KEY_PATH=./keys/private.pem
JWT_PUBLIC_KEY_PATH=./keys/public.pem
JWT_ALGORITHM=RS256

# Storage
S3_BUCKET=sales-agent-files
AWS_REGION=us-east-1

# Observability
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
SENTRY_DSN=
```

---

## Day-by-Day Milestones

| Day | Dev 1 | Dev 2 | Dev 3 | Dev 4 |
|---|---|---|---|---|
| 1 | Port interfaces committed. Docker Compose drafted. | Read architecture §3. Stub use case. | Read architecture §4. Stub extractors. | JWT middleware committed. Next.js app running. |
| 2 | DB migrations runnable. Redis+Qdrant+NATS up. | Intent classifier wired (vLLM). Embedding cache working. | File upload + ClamAV scan working. | Auth endpoints live. Basic lead list page. |
| 3 | Health endpoints live. Seeding scripts for all 3 Qdrant collections. | Full P1 pipeline (no WebSocket yet). Suggestions in Celery. | PDF/DOCX/PPTX extractors working. Text cleaner done. | WebSocket client. Paste → 202 flow in UI. |
| 4 | CDC/Debezium pipeline running. Indexing worker tested. | WebSocket/SSE delivery. Redis cache for suggestions. | GPT-4.1 extraction agent. Gap detector. | Suggestion cards rendering. Prometheus scraping. |
| 5 | Feedback loop: Qdrant payload update on selection. | P1 pipeline fully tested. Tone validator. Feedback loop. | Claude Sonnet 4.6 enrichment with tool_use. | File upload UI. Requirements editor skeleton. |
| 6 | Admin review queue data model complete. | Prompt eval suite passing (50 test cases). | Pricing DB lookup. Budget estimator. | Admin dashboard health panel. Grafana dashboards. |
| 7 | Vector DB management API endpoints. | P1 A/B test framework. Prompt YAML loading. | Resource matching. Requirements doc renderer. | Vector DB portal UI. Review queue UI. |
| 8 | Re-embedding pipeline. Orphan detection. | Load test P1 at 100 concurrent users. | Proposal PDF generation. Human approval gate. | CI/CD pipeline. K8s manifests. Cost dashboard. |

---

## Integration Points

```
Dev 4 (Auth)  ────────────────────────────────► All devs (import require_auth)
Dev 1 (Ports) ────────────────────────────────► Dev 2 + Dev 3 (implement against VectorStorePort)
Dev 1 (docker-compose) ───────────────────────► Dev 2 + Dev 3 (local dev environment)
Dev 2 (anthropic_client.py) ──────────────────► Dev 3 (reuse for Claude enrichment agent)
Dev 2 (WebSocket push) ───────────────────────► Dev 4 (frontend consumes suggestion stream)
Dev 3 (requirements approval event) ──────────► Dev 4 (frontend approval gate UI)
```