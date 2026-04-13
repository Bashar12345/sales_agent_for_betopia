# API Route Ownership

| File | Owner | Pipeline |
|---|---|---|
| `health.py` | **Zohra** | P3 — readiness + liveness probes |
| `input.py` | **Niloy** | P1 — paste client message |
| `suggestions.py` | **Niloy** | P1 — get/select suggestions, SSE stream |
| `conversations.py` | **Niloy** | P1 — chat history, WebSocket push |
| `requirements.py` | **Asif** | P2 — file ingest, extraction status |
| `proposals.py` | **Asif** | P2 — generate + approve proposal PDF |
| `quotations.py` | **Asif** | P2 — quotation templates + pricing |
| `resources.py` | **Asif** | P2 — developer resource matching |
| `leads.py` | **Bashar** | Shared — CRUD for leads |
| `replies.py` | **Bashar** | Legacy (deprecated; use `/input` + `/suggestions`) |
| `router.py` | **Bashar** | Wires all sub-routers together |
| `integrations/odoo.py` | **Bashar** | ERP sync (future) |
