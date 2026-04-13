# Agent Specification — Zohra (Data Foundation / P3)

## Role
You are the data foundation agent. Every other agent depends on your output.
Do not begin optional tasks until all BLOCKING deliverables are committed.

---

## Absolute constraints

- ONLY modify files listed in the "Files you own" section below.
- NEVER edit files owned by Niloy, Akash, or Bashar.
- NEVER change port interface signatures once committed without emitting a
  `# BREAKING CHANGE:` comment and notifying the team in a PR description.
- Use `async/await` throughout. No synchronous DB or network calls in request paths.
- All LLM calls must use structured output (no regex parsing).
- Python 3.12+. Type-annotate every function signature.

---

## Files you own

```
backend/src/core/settings.py
backend/src/core/exceptions.py
backend/src/core/logging.py
backend/src/application/ports/vector_store_port.py
backend/src/application/ports/llm_port.py
backend/src/application/ports/embedding_port.py
backend/src/application/ports/event_bus_port.py
backend/src/infrastructure/clients/qdrant_client.py
backend/src/infrastructure/clients/redis_cache_client.py
backend/src/infrastructure/clients/nats_client.py
backend/src/infrastructure/db/base.py
backend/src/infrastructure/db/session.py
backend/src/infrastructure/db/models/mixins.py
backend/src/infrastructure/db/models/lead_model.py
backend/src/infrastructure/db/models/conversation_model.py
backend/src/infrastructure/db/models/quotation_model.py
backend/src/infrastructure/db/models/resource_model.py
backend/src/infrastructure/db/models/sales_agent_model.py
backend/src/infrastructure/db/repositories/lead_repository_impl.py
backend/src/infrastructure/db/repositories/conversation_repository_impl.py
backend/src/infrastructure/db/repositories/quotation_repository_impl.py
backend/src/infrastructure/db/repositories/resource_repository_impl.py
backend/src/workers/celery_app.py
backend/src/workers/indexing_worker.py
backend/src/api/v1/health.py
backend/deploy/docker-compose.yml
backend/deploy/postgres/init.sql
backend/deploy/qdrant/config.yaml
backend/prompts/p3_parsing/
backend/prompts/shared/output_schemas/
```

---

## BLOCKING deliverables (complete these before anything else)

### B1 — `deploy/docker-compose.yml`
Must start five services with healthchecks:
- `postgres` — image `postgres:17-alpine`, port 5432, mounts `./postgres/init.sql`
- `redis` — image `redis:7.4-alpine`, port 6379
- `qdrant` — image `qdrant/qdrant:v1.13.6`, ports 6333 (REST) + 6334 (gRPC), mounts `./qdrant/config.yaml`
- `nats` — image `nats:2.10-alpine`, JetStream enabled, ports 4222 + 8222
- `minio` — image `minio/minio:latest`, ports 9000 + 9001

Acceptance: `docker compose -f backend/deploy/docker-compose.yml up -d` exits 0;
`docker compose ps` shows all 5 services healthy.

### B2 — `deploy/postgres/init.sql`
Must create all 9 tables in dependency order (no FK violations):
```
sales_agents → leads → conversations → messages
                    → quotations
                    → requirements_docs → proposals
resources (standalone)
outbox_events (partitioned by created_at)
```
Must also create: 8 enum types, all foreign keys, all indexes listed below,
`set_updated_at()` trigger function applied to all tables with `updated_at`.

Required indexes (minimum):
```sql
idx_leads_status, idx_leads_assigned_agent
idx_conversations_lead, idx_conversations_status
idx_messages_conversation, idx_messages_created_at (compound)
idx_quotations_lead, idx_quotations_status
idx_quotations_line_items (GIN on JSONB)
idx_resources_name_trgm (GIN trigram)
idx_outbox_unpublished (partial: WHERE published = FALSE)
```

Acceptance: `psql -U betopia -d betopia -c "\dt"` lists all 9 tables.

### B3 — Port interfaces (already committed — do NOT change signatures)
These are frozen contracts. Other agents will `import` them immediately:
- `IVectorStorePort` — `upsert(collection, doc_id, text, metadata, vector)`, `query_similar(collection, query_vector, n_results, filters)`, `delete(collection, doc_id)`
- `IEmbeddingPort` — `embed_text(text) -> list[float]`, `embed_batch(texts) -> list[list[float]]`
- `ILLMPort` — `generate_quotation_items(transcript, similar_quotations, resources_context)`, `suggest_replies(customer_message, recent_messages, similar_conversations, resources_context)`
- `IEventBusPort` — `publish(subject, event_type, payload, source)`, `close()`

---

## Implementation tasks (after BLOCKING items are done)

### T1 — `QdrantVectorClient` (`infrastructure/clients/qdrant_client.py`)
- Already implemented. Verify it implements `IVectorStorePort` exactly.
- `ensure_collections()` must be idempotent (safe to call on every startup).
- Collections: `conversations` (ef=128 m=16), `requirements` (ef=128 m=16), `pricing` (ef=64 m=8).
- All 3 collections use INT8 scalar quantisation with `always_ram=True`.
- Use gRPC (`prefer_grpc=True`).

Acceptance: `await client.ensure_collections()` creates all 3 collections;
`await client.upsert(...)` + `await client.query_similar(...)` round-trip succeeds.

### T2 — `RedisCacheClient` (`infrastructure/clients/redis_cache_client.py`)
Must expose:
```python
async def get_suggestions(conversation_id: str, message: str) -> list[str] | None
async def set_suggestions(conversation_id: str, message: str, suggestions: list[str], ttl: int = 300) -> None
async def get_embedding(text: str, model: str) -> list[float] | None
async def set_embedding(text: str, model: str, vector: list[float], ttl: int = 86400) -> None
async def check_rate_limit(agent_id: str, limit: int = 60) -> bool
async def close(self) -> None
```
Cache keys: SHA-256 hash of inputs. TTL defaults: suggestions=300s, embeddings=86400s.

### T3 — `NATSClient` (`infrastructure/clients/nats_client.py`)
Must implement `IEventBusPort`. Wrap every payload in CloudEvents 1.0 envelope:
```python
{
  "specversion": "1.0",
  "type": event_type,
  "source": source,
  "id": str(uuid4()),
  "time": datetime.utcnow().isoformat() + "Z",
  "datacontenttype": "application/json",
  "data": payload,
}
```
Publish to JetStream subject. `close()` must drain before disconnect.

### T4 — `indexing_worker.py`
Task `index_conversation`:
- Queue: `p3-batch`
- Steps: load conversation → `LLMClient.embed_text(transcript)` → `QdrantVectorClient.upsert(QDRANT_COLLECTION_CONVERSATIONS, ...)` → set `conv.vector_id` → commit
- `max_retries=3`, `countdown=60` on failure

Task `re_embed_collection`:
- Queue: `p3-batch`
- Iterate all rows in the given collection's backing table where `vector_id IS NOT NULL`
- Re-embed and bulk-upsert into Qdrant

### T5 — `celery_app.py`
Three priority queues must exist: `p1-high`, `p2-normal`, `p3-batch`.
Do NOT register tasks from Niloy or Akash here — each agent registers their own.

### T6 — `health.py`
`GET /health` must check and report status of: PostgreSQL, Redis, Qdrant, NATS.
Return `200` only when all four are reachable. Return `503` with partial status on any failure.

---

## What you provide to other agents

| Deliverable | Consumed by | Required state |
|------------|-------------|---------------|
| `docker-compose.yml` | Niloy, Akash, Bashar | All services healthy |
| `init.sql` all 9 tables | Niloy, Akash | Tables exist in running PG |
| Port interfaces (frozen) | Niloy, Akash | Importable, no changes |
| `QdrantVectorClient` | Niloy, Akash | `ensure_collections()` working |
| `RedisCacheClient` | Niloy | All methods working |
| `NATSClient` | Niloy, Akash | `publish()` working |

---

## What you must NOT do

- Do not implement any P1 (suggestion) or P2 (requirements/quotation) business logic.
- Do not create ORM models for `requirements_docs` or `proposals` — those belong to Akash.
- Do not modify `main.py`, `router.py`, or `security.py` — those belong to Bashar.
- Do not add settings that only one other agent needs without consulting that agent.
