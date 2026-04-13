# Infrastructure Layer Ownership

## clients/

| File | Owner | Notes |
|---|---|---|
| `qdrant_client.py` | **Zohra** | Vector DB — 3 collections, HNSW, scalar quant |
| `redis_cache_client.py` | **Zohra** | Suggestion cache (5 min) + embedding cache (24 h) |
| `nats_client.py` | **Zohra** | CloudEvents event bus — publish/subscribe |
| `llm_client.py` | **Niloy** | GPT-4.1 structured outputs + fallback chain |
| `vllm_client.py` | **Niloy** | In-house vLLM — intent classify + tone validate |
| `anthropic_client.py` | **Niloy** | Claude Sonnet 4.6 — P1 fallback + P2 enrichment |
| `document_generator.py` | **Asif** | WeasyPrint + ReportLab PDF renderer |

## db/

| Directory / File | Owner | Notes |
|---|---|---|
| `base.py`, `session.py` | **Zohra** | SQLAlchemy async engine + session factory |
| `models/` | **Zohra** | All ORM models (9 core tables) |
| `repositories/` | **Zohra** | All repository implementations |
| `migrations/` | **Zohra** | Alembic migration files |
