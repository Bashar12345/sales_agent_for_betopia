# Workers Ownership

| File | Owner | Tasks registered |
|---|---|---|
| `celery_app.py` | **Dev 1** | Celery factory — priority queues: `p1-high`, `p2-normal`, `p3-batch` |
| `indexing_worker.py` | **Dev 1** | `embed_and_upsert`, `re_embed_collection` |
| `quotation_worker.py` | **Dev 3** | `extract_requirements`, `enrich_requirements`, `generate_quotation_doc` |

> Dev 2 adds `suggestion_worker.py` for `run_p1_pipeline(message_id)`.
