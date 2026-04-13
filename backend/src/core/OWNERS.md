# Core Module Ownership

| File | Owner | Notes |
|---|---|---|
| `settings.py` | **Dev 1** | All env vars via Pydantic Settings — edit here to add config |
| `exceptions.py` | **Dev 1** | Domain + infra exception hierarchy — add new exception types here |
| `logging.py` | **Dev 1** | structlog JSON setup + OpenTelemetry trace context |
| `security.py` | **Dev 4** | JWT RS256 middleware — `require_auth` and `require_role` FastAPI deps |

> **All devs import from `core/`** — coordinate with the owner before changing these files.
