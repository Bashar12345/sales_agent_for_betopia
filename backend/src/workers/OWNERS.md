# Workers Ownership

| File | Owner | Tasks registered |
|---|---|---|
| `celery_app.py` | **Zohra** | Celery factory — priority queues: `p1-high`, `p2-normal`, `p3-batch` |
| `indexing_worker.py` | **Zohra** | `embed_and_upsert`, `re_embed_collection` |
| `quotation_worker.py` | **Asif** | `extract_requirements`, `enrich_requirements`, `generate_quotation_doc` |

> Niloy adds `suggestion_worker.py` for `run_p1_pipeline(message_id)`.
