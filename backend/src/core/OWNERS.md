# Core Module Ownership

| File | Owner | Notes |
|---|---|---|
| `settings.py` | **Zohra** | All env vars via Pydantic Settings — edit here to add config |
| `exceptions.py` | **Zohra** | Domain + infra exception hierarchy — add new exception types here |
| `logging.py` | **Zohra** | structlog JSON setup + OpenTelemetry trace context |
| `security.py` | **Bashar** | JWT RS256 middleware — `require_auth` and `require_role` FastAPI deps |

> **All devs import from `core/`** — coordinate with the owner before changing these files.
