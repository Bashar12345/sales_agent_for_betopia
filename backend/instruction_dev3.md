# Agent Specification — Asif (P2 Requirements Agent)

## Role
You build the requirements extraction and quotation generation pipeline.
A conversation transcript is processed by LLM to produce a structured
requirements document, a priced quotation, and a downloadable proposal PDF.

---

## Absolute constraints

- ONLY modify files listed in the "Files you own" section below.
- NEVER edit port interface files owned by Zohra (`application/ports/`).
- NEVER call `ChromaDBClient` — it is deprecated. Use `QdrantVectorClient` via `IVectorStorePort`.
- NEVER call `settings.CHROMA_COLLECTION_*` — use `settings.QDRANT_COLLECTION_*`.
- All LLM calls must use structured output. No regex parsing of LLM responses.
- Use `async/await` throughout. Type-annotate every function signature.
- Python 3.12+.

---

## Files you own

```
backend/src/api/v1/requirements.py
backend/src/api/v1/proposals.py
backend/src/api/v1/quotations.py
backend/src/api/v1/resources.py
backend/src/application/use_cases/process_fiverr_lead.py
backend/src/application/use_cases/generate_quotation.py
backend/src/application/use_cases/upload_resource.py
backend/src/application/dto/quotation_dto.py
backend/src/application/dto/resource_dto.py
backend/src/application/ports/document_generator_port.py
backend/src/domain/services/quotation_service.py
backend/src/domain/entities/requirements_doc.py
backend/src/domain/entities/proposal.py
backend/src/domain/entities/quotation.py
backend/src/domain/entities/resource.py
backend/src/domain/repositories/quotation_repository.py
backend/src/domain/repositories/resource_repository.py
backend/src/infrastructure/clients/document_generator.py
backend/src/workers/quotation_worker.py
backend/prompts/p2_extraction/
```

## Files you must CREATE (ORM models not yet written)

```
backend/src/infrastructure/db/models/requirements_doc_model.py
backend/src/infrastructure/db/models/proposal_model.py
backend/src/infrastructure/db/repositories/requirements_doc_repository_impl.py
backend/src/infrastructure/db/repositories/proposal_repository_impl.py
```

---

## Prerequisite: wait for these before starting

| Item | Owner | How to verify |
|------|-------|--------------|
| `docker-compose.yml` running | Zohra | `docker compose ps` → all 5 healthy |
| `init.sql` tables exist | Zohra | `psql -c "\dt"` lists `requirements_docs`, `proposals` |
| `IVectorStorePort` frozen | Zohra | Importable from `application.ports.vector_store_port` |
| `ILLMPort` frozen | Zohra | Importable from `application.ports.llm_port` |
| `IEventBusPort` frozen | Zohra | Importable from `application.ports.event_bus_port` |
| `require_auth` + `require_role` | Bashar | Importable from `src.core.security` |

---

## P2 pipeline — exact implementation spec

### Step 1: Requirements extraction

Endpoint: `POST /api/v1/requirements/extract`

Request:
```python
class ExtractRequest(BaseModel):
    conversation_id: UUID
```

Implementation (ordered):
```
1. Load conversation + full message transcript from DB
2. vector = await embedding_client.embed_text(transcript)
3. similar_reqs = await vector_store.query_similar(
       collection=settings.QDRANT_COLLECTION_REQUIREMENTS,
       query_vector=vector,
       n_results=3,
   )
4. raw = await llm_client.extract_requirements(
       transcript=transcript,
       similar_requirements=[r["text"] for r in similar_reqs],
   )
   # structured output → RequirementsDoc schema
5. Persist RequirementsDocModel to PostgreSQL
6. Index into Qdrant:
   await vector_store.upsert(
       collection=settings.QDRANT_COLLECTION_REQUIREMENTS,
       doc_id=str(req_doc.id),
       text=req_doc.summary_text(),
       metadata={"lead_id": str(req_doc.lead_id)},
       vector=await embedding_client.embed_text(req_doc.summary_text()),
   )
7. Enqueue enrichment:
   enrich_requirements.apply_async(args=[str(req_doc.id)], queue="p2-normal")
8. Emit NATS event:
   await event_bus.publish("requirements.extracted", "requirements.extracted",
       {"requirements_doc_id": str(req_doc.id), "lead_id": str(lead_id)})
```

### Step 2: Enrichment (Celery task `enrich_requirements`)

```
1. Load RequirementsDocModel
2. LLM enrichment call → add confidence_score, clarifying_questions, risk_flags
   Structured output matching requirements_v1.json schema
3. budget_estimate = await budget_estimator(enriched_data, pricing_context)
   (query QDRANT_COLLECTION_PRICING for similar past quotations)
4. Update RequirementsDocModel with enriched_data + budget_estimate
5. Enqueue generate_quotation_doc.apply_async(args=[str(req_doc.id)], queue="p2-normal")
```

### Step 3: Quotation generation (`POST /api/v1/quotations/generate`)

Request:
```python
class GenerateQuotationRequest(BaseModel):
    requirements_doc_id: UUID
```

Implementation:
```
1. Load RequirementsDocModel + conversation transcript
2. similar_quotations = await vector_store.query_similar(
       collection=settings.QDRANT_COLLECTION_PRICING,
       query_vector=embedding_of_summary,
       n_results=5,
   )
3. line_items, summary = await llm_client.generate_quotation_items(
       transcript=transcript,
       similar_quotations=[q["text"] for q in similar_quotations],
       resources_context=resource_texts,
   )
4. Persist QuotationModel (total_amount = sum of line_items)
5. Index into QDRANT_COLLECTION_PRICING for future similarity
6. Trigger PDF generation:
   generate_quotation_doc.apply_async(args=[str(quotation_id)], queue="p2-normal")
7. Emit NATS: quotations.generated
```

### Step 4: Proposal PDF (`generate_quotation_doc` Celery task)

```
1. Load QuotationModel + RequirementsDocModel + LeadModel
2. Call document_generator.generate_proposal_pdf(quotation, requirements_doc, lead)
   → returns absolute path to PDF file
3. Persist ProposalModel with pdf_path + status=ready
4. Emit NATS: quotations.generated (update with pdf_path)
```

---

## ORM models to create

### `requirements_doc_model.py`
Table: `requirements_docs` (schema already in `init.sql`).
Columns: `id (UUID PK)`, `conversation_id (FK)`, `lead_id (FK)`, `raw_extraction (JSONB)`,
`enriched_data (JSONB)`, `budget_estimate (NUMERIC)`, `confidence_score (NUMERIC)`,
`created_at`, `updated_at`.

### `proposal_model.py`
Table: `proposals` (schema already in `init.sql`).
Columns: `id (UUID PK)`, `quotation_id (FK)`, `requirements_doc_id (FK nullable)`,
`lead_id (FK)`, `agent_id (FK)`, `title`, `executive_summary`, `valid_days`,
`status (prop_status enum)`, `pdf_path`, `download_token`, `odoo_order_id`,
`created_at`, `updated_at`.

Use `PGUUID(as_uuid=False)` for all UUID columns (matches other models).
Import base from `src.infrastructure.db.base`.

---

## Celery tasks to register in `quotation_worker.py`

| Task name | Queue | Input | Output |
|-----------|-------|-------|--------|
| `extract_requirements` | `p2-normal` | `conversation_id: str` | Creates RequirementsDocModel |
| `enrich_requirements` | `p2-normal` | `requirements_doc_id: str` | Updates RequirementsDocModel |
| `generate_quotation_doc` | `p2-normal` | `quotation_id: str` | Creates ProposalModel + PDF |

All tasks: `bind=True, max_retries=3`, `countdown=60` on retry.

---

## Resource upload flow

Endpoint: `POST /api/v1/resources/upload` (multipart/form-data)

```
1. Parse file: PDF → pdfplumber, DOCX → python-docx, URL → httpx fetch
2. Store file binary in MinIO via minio_client (bucket: "resources")
3. Persist ResourceModel (content=extracted_text, file_path=minio_key)
4. Embed + index into Qdrant:
   await vector_store.upsert(
       collection=settings.QDRANT_COLLECTION_REQUIREMENTS,
       doc_id=str(resource.id),
       text=resource.content,
       metadata={"type": resource.resource_type},
       vector=await embedding.embed_text(resource.content),
   )
```

---

## Routes to implement

```
POST /api/v1/requirements/extract           trigger extraction for a conversation
GET  /api/v1/requirements/{id}              get requirements doc
POST /api/v1/quotations/generate            generate quotation from requirements doc
GET  /api/v1/quotations/{id}               get quotation
PATCH /api/v1/quotations/{id}              update status (require_role: SALES_MANAGER)
GET  /api/v1/proposals/{id}               get proposal + download token
POST /api/v1/resources/upload              upload knowledge base document
GET  /api/v1/resources                    list resources
DELETE /api/v1/resources/{id}             delete resource (require_role: ADMIN)
```

All routes require `Depends(require_auth)`. Approval routes require `require_role(AgentRole.SALES_MANAGER)`.

---

## Structured output schemas

| Schema file | LLM call |
|-------------|---------|
| `prompts/shared/output_schemas/requirements_v1.json` | extraction step |
| *(create)* `prompts/shared/output_schemas/quotation_line_items_v1.json` | quotation generation |

Schema for `quotation_line_items_v1.json`:
```json
{
  "line_items": [
    { "description": "str", "quantity": 1, "unit_price": 0.0, "category": "str" }
  ],
  "executive_summary": "str"
}
```

---

## Prompts (`prompts/p2_extraction/`)

| File | Must contain |
|------|-------------|
| `v1_extraction_prompt.yaml` | `version`, extraction prompt with `{transcript}`, `{similar_requirements}` placeholders |
| `v1_enrichment_prompt.yaml` | `version`, enrichment with confidence + risk scoring |
| `v1_budget_estimator.yaml` | `version`, budget estimation using `{enriched_data}`, `{pricing_context}` |

Rule: increment `version` before any edit. Run eval suite. Never deploy unvalidated prompts.

---

## Acceptance criteria

| Check | Pass condition |
|-------|---------------|
| Extraction | `RequirementsDocModel` created with non-empty `raw_extraction` JSONB |
| Enrichment | `confidence_score` is a float 0.0–1.0; `budget_estimate` > 0 |
| Quotation | `line_items` JSONB array has ≥ 1 item; `total_amount` = sum of line items |
| PDF | `ProposalModel.pdf_path` points to a file that exists on disk / MinIO |
| Qdrant indexing | All 3 Qdrant collections queryable after pipeline runs |
| NATS events | `requirements.extracted` and `quotations.generated` events appear in NATS |

---

## What you must NOT do

- Do not implement P1 (suggestion) logic.
- Do not modify `lead_model.py`, `conversation_model.py`, or any model not in your list.
- Do not modify port interfaces in `application/ports/`.
- Do not touch `celery_app.py` factory — only register tasks in `quotation_worker.py`.
- Do not write to the `conversations` or `messages` tables directly.
