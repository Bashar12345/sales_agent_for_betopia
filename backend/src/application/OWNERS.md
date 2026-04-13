# Application Layer Ownership

## use_cases/

| File | Owner | What it orchestrates |
|---|---|---|
| `suggest_replies.py` | **Dev 2** | Full P1 pipeline: intent → embed → search → GPT-4.1 → format → cache |
| `process_fiverr_lead.py` | **Dev 3** | Full P2 pipeline: ingest → extract → enrich → estimate → review gate |
| `generate_quotation.py` | **Dev 3** | Budget + timeline estimation from Pricing DB |
| `upload_resource.py` | **Dev 3** | File upload: MIME check + ClamAV scan + S3 store |

## ports/ (interfaces — Dev 1 writes, everyone implements/consumes)

| File | Owner | Used by |
|---|---|---|
| `vector_store_port.py` | **Dev 1** | Dev 2 (P1 search), Dev 3 (P2 search) |
| `llm_port.py` | **Dev 1** | Dev 2 (implements LLMClient), Dev 3 (implements AnthropicClient) |
| `document_generator_port.py` | **Dev 3** | Dev 3 (implements WeasyPrint renderer) |
| `fiverr_port.py` | **Dev 3** | Deprecated — no direct Fiverr API calls allowed |
| `odoo_port.py` | **Dev 4** | Future ERP integration |

## dto/

| File | Owner |
|---|---|
| `reply_dto.py`, `conversation_dto.py` | **Dev 2** |
| `quotation_dto.py`, `resource_dto.py` | **Dev 3** |
| `lead_dto.py` | **Dev 4** |
