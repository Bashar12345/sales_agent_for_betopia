# API Route Ownership

| File | Owner | Pipeline |
|---|---|---|
| `health.py` | **Dev 1** | P3 — readiness + liveness probes |
| `input.py` | **Dev 2** | P1 — paste client message |
| `suggestions.py` | **Dev 2** | P1 — get/select suggestions, SSE stream |
| `conversations.py` | **Dev 2** | P1 — chat history, WebSocket push |
| `requirements.py` | **Dev 3** | P2 — file ingest, extraction status |
| `proposals.py` | **Dev 3** | P2 — generate + approve proposal PDF |
| `quotations.py` | **Dev 3** | P2 — quotation templates + pricing |
| `resources.py` | **Dev 3** | P2 — developer resource matching |
| `leads.py` | **Dev 4** | Shared — CRUD for leads |
| `replies.py` | **Dev 4** | Legacy (deprecated; use `/input` + `/suggestions`) |
| `router.py` | **Dev 4** | Wires all sub-routers together |
| `integrations/odoo.py` | **Dev 4** | ERP sync (future) |
