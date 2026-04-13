# Infrastructure Layer Ownership

## clients/

| File | Owner | Notes |
|---|---|---|
| `qdrant_client.py` | **Dev 1** | Vector DB — 3 collections, HNSW, scalar quant |
| `redis_cache_client.py` | **Dev 1** | Suggestion cache (5 min) + embedding cache (24 h) |
| `nats_client.py` | **Dev 1** | CloudEvents event bus — publish/subscribe |
| `llm_client.py` | **Dev 2** | GPT-4.1 structured outputs + fallback chain |
| `vllm_client.py` | **Dev 2** | In-house vLLM — intent classify + tone validate |
| `anthropic_client.py` | **Dev 2** | Claude Sonnet 4.6 — P1 fallback + P2 enrichment |
| `document_generator.py` | **Dev 3** | WeasyPrint + ReportLab PDF renderer |

## db/

| Directory / File | Owner | Notes |
|---|---|---|
| `base.py`, `session.py` | **Dev 1** | SQLAlchemy async engine + session factory |
| `models/` | **Dev 1** | All ORM models (9 core tables) |
| `repositories/` | **Dev 1** | All repository implementations |
| `migrations/` | **Dev 1** | Alembic migration files |
