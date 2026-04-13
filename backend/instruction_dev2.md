# Agent Specification — Dev 2 (P1 Conversation Engine)

## Role
You build the real-time reply suggestion pipeline. A salesman submits a
customer message; you return 5 ranked reply candidates in under 5 seconds.

---

## Absolute constraints

- ONLY modify files listed in the "Files you own" section below.
- NEVER edit port interface files owned by Dev 1 (`application/ports/`).
- NEVER call `ChromaDBClient` — it is deprecated. Use `QdrantVectorClient` via `IVectorStorePort`.
- NEVER call `settings.CHROMA_COLLECTION_*` — use `settings.QDRANT_COLLECTION_*`.
- All LLM calls must use structured output. No regex parsing of LLM responses.
- P95 latency for `POST /api/v1/input` must be < 5 seconds.
- Use `async/await` throughout. Type-annotate every function signature.
- Python 3.12+.

---

## Files you own

```
backend/src/api/v1/input.py
backend/src/api/v1/suggestions.py
backend/src/api/v1/conversations.py
backend/src/application/use_cases/suggest_replies.py
backend/src/application/dto/reply_dto.py
backend/src/application/dto/conversation_dto.py
backend/src/domain/services/reply_service.py
backend/src/domain/entities/suggestion.py
backend/src/domain/entities/message.py
backend/src/domain/entities/conversation.py
backend/src/domain/repositories/conversation_repository.py
backend/src/infrastructure/clients/llm_client.py
backend/src/infrastructure/clients/vllm_client.py
backend/src/infrastructure/clients/anthropic_client.py
backend/prompts/p1_suggestion/
backend/prompts/shared/system_persona.yaml
```

---

## Prerequisite: wait for these before starting

| Item | Owner | How to verify |
|------|-------|--------------|
| `docker-compose.yml` running | Dev 1 | `docker compose ps` → all 5 healthy |
| `IVectorStorePort` frozen | Dev 1 | File exists at `application/ports/vector_store_port.py` |
| `IEmbeddingPort` frozen | Dev 1 | File exists at `application/ports/embedding_port.py` |
| `RedisCacheClient` working | Dev 1 | Can import and call `get_suggestions()` |
| `require_auth` dependency | Dev 4 | Can import from `src.core.security` |

---

## P1 pipeline — exact implementation spec

### Endpoint: `POST /api/v1/input`

Request body:
```python
class InputRequest(BaseModel):
    conversation_id: UUID
    customer_message: str
```

Response body:
```python
class SuggestionListDTO(BaseModel):
    suggestions: list[SuggestionDTO]  # exactly 5 items
    cached: bool
    latency_ms: int

class SuggestionDTO(BaseModel):
    text: str
    tone: str        # professional | friendly | technical | empathetic
    confidence: float  # 0.0 – 1.0
```

### `SuggestReplies` use case — exact steps (in order)

```
1. cache_client.get_suggestions(conversation_id, customer_message)
   → if HIT: return immediately with cached=True

2. Load last 10 messages of conversation from DB (ConversationRepositoryImpl)

3. vector = await llm_client.embed_text(customer_message)

4. similar_convs = await vector_store.query_similar(
       collection=settings.QDRANT_COLLECTION_CONVERSATIONS,
       query_vector=vector,
       n_results=5,
   )

5. resource_chunks = await vector_store.query_similar(
       collection=settings.QDRANT_COLLECTION_PRICING,
       query_vector=vector,
       n_results=3,
   )

6. suggestions = await llm_client.suggest_replies(
       customer_message=customer_message,
       recent_messages=last_10_messages,
       similar_conversations=[s["text"] for s in similar_convs],
       resources_context=[r["text"] for r in resource_chunks],
   )

7. await cache_client.set_suggestions(conversation_id, customer_message, suggestions)

8. await event_bus.publish(
       subject="conversations.updated",
       event_type="conversation.message.received",
       payload={"conversation_id": str(conversation_id)},
   )

9. Return SuggestionListDTO
```

---

## LLM client — exact implementation spec (`llm_client.py`)

Must implement `ILLMPort` and `IEmbeddingPort`.

### Fallback chain for `suggest_replies`
```
GPT-4.1 (primary)
  → on timeout > 3s or rate limit: Claude Sonnet 4.6 (anthropic_client.py)
  → on timeout > 3s: vLLM in-house (vllm_client.py)
```
Use `tenacity` for retries. Max 2 retries per provider before falling back.

### Structured output schema
LLM must return JSON matching `prompts/shared/output_schemas/suggestion_list_v1.json`.
Pass the schema as a JSON Schema tool / response_format constraint — never parse free text.

### `embed_text` / `embed_batch`
Model: `text-embedding-3-large`. Dimensions: `settings.EMBEDDING_DIMENSIONS` (3072).
Check embedding cache BEFORE calling the API:
```python
cached_vec = await cache_client.get_embedding(text, model="text-embedding-3-large")
if cached_vec:
    return cached_vec
vector = await openai_client.embed(text)
await cache_client.set_embedding(text, "text-embedding-3-large", vector)
return vector
```

---

## Conversation closing — trigger P3 indexing

When `PATCH /api/v1/conversations/{id}` sets `status=closed`, you must enqueue:
```python
from src.workers.indexing_worker import index_conversation

index_conversation.apply_async(
    args=[str(conversation_id)],
    queue="p3-batch",
)
```

---

## Prompts (`prompts/p1_suggestion/`)

Files you must maintain:

| File | Must contain |
|------|-------------|
| `v1_suggestion_prompt.yaml` | `version`, `model`, `system`, `user` template with `{customer_message}`, `{recent_messages}`, `{similar_conversations}`, `{resources_context}` placeholders |
| `v1_tone_validator.yaml` | Post-generation tone classification prompt |
| `eval_suite.yaml` | ≥ 10 test cases; must pass before any prompt change is merged |

Rule: increment `version` field before any prompt edit. Run eval suite. Never deploy unvalidated prompts.

---

## Routes to implement

```
POST   /api/v1/input                     submit customer message → 5 suggestions
GET    /api/v1/suggestions/{conv_id}     get suggestions for a conversation
GET    /api/v1/conversations             list conversations for current agent
GET    /api/v1/conversations/{id}        get conversation + messages
POST   /api/v1/conversations             create new conversation for a lead
PATCH  /api/v1/conversations/{id}        update status (active|paused|closed|quoted)
```

All routes require `Depends(require_auth)` from `src.core.security` (Dev 4).

---

## Acceptance criteria

| Check | Pass condition |
|-------|---------------|
| Latency (cold) | P95 < 5 000 ms with no cache |
| Latency (warm) | P95 < 500 ms on cache hit |
| Output count | Always returns exactly 5 suggestions |
| Structured output | No suggestion ever contains raw JSON or XML |
| Cache hit rate | ≥ 40% after 100 requests (same conv, repeated messages) |
| Fallback | When `OPENAI_API_KEY` is invalid, Claude Sonnet 4.6 is used |
| Indexing | `index_conversation` task is enqueued exactly once when conv closes |

---

## What you must NOT do

- Do not implement any P2 (requirements / quotation) logic.
- Do not write to `quotations`, `requirements_docs`, or `proposals` tables.
- Do not modify port interfaces in `application/ports/`.
- Do not read `settings.CHROMA_COLLECTION_*` — those settings no longer exist.
- Do not change the Celery `celery_app.py` factory — only register your own tasks.
