# Application Layer Ownership

## use_cases/

| File | Owner | What it orchestrates |
|---|---|---|
| `suggest_replies.py` | **Niloy** | Full P1 pipeline: intent → embed → search → GPT-4.1 → format → cache |
| `process_fiverr_lead.py` | **Asif** | Full P2 pipeline: ingest → extract → enrich → estimate → review gate |
| `generate_quotation.py` | **Asif** | Budget + timeline estimation from Pricing DB |
| `upload_resource.py` | **Asif** | File upload: MIME check + ClamAV scan + S3 store |

## ports/ (interfaces — Zohra writes, everyone implements/consumes)

| File | Owner | Used by |
|---|---|---|
| `vector_store_port.py` | **Zohra** | Niloy (P1 search), Asif (P2 search) |
| `llm_port.py` | **Zohra** | Niloy (implements LLMClient), Asif (implements AnthropicClient) |
| `document_generator_port.py` | **Asif** | Asif (implements WeasyPrint renderer) |
| `fiverr_port.py` | **Asif** | Deprecated — no direct Fiverr API calls allowed |
| `odoo_port.py` | **Bashar** | Future ERP integration |

## dto/

| File | Owner |
|---|---|
| `reply_dto.py`, `conversation_dto.py` | **Niloy** |
| `quotation_dto.py`, `resource_dto.py` | **Asif** |
| `lead_dto.py` | **Bashar** |
