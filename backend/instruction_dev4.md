# Agent Specification — Dev 4 (Frontend, Auth & DevOps)

## Role
You own three distinct areas: (1) JWT RS256 auth middleware — the single most
blocking item for Dev 2 and Dev 3, land it first; (2) Next.js 15 frontend;
(3) CI/CD workflows and Kubernetes manifests.

---

## Absolute constraints

- ONLY modify files listed in the "Files you own" section below.
- NEVER edit `src/core/settings.py`, `src/application/ports/`, or any
  file owned by Dev 1, Dev 2, or Dev 3.
- `require_auth` and `require_role` must be pure FastAPI dependencies (no side effects).
- JWT algorithm must be RS256 (asymmetric). Never use HS256.
- All frontend API calls must go through `NEXT_PUBLIC_API_URL`. No hard-coded URLs.
- Type-annotate every Python function signature. Python 3.12+.
- Frontend: TypeScript strict mode. No `any` types.

---

## Files you own

```
backend/src/main.py
backend/src/core/security.py
backend/src/api/v1/router.py
backend/src/api/v1/leads.py
backend/src/api/v1/replies.py
backend/src/api/v1/integrations/__init__.py
backend/src/api/v1/integrations/odoo.py
backend/src/application/dto/lead_dto.py
backend/src/domain/entities/lead.py
backend/src/domain/entities/fiverr_profile.py
backend/src/domain/entities/sales_agent.py
backend/src/domain/repositories/lead_repository.py
backend/observability/
backend/deploy/k8s/
backend/deploy/docker/app.Dockerfile
backend/deploy/docker/worker.Dockerfile
backend/deploy/nginx/
backend/.github/workflows/ci.yml
backend/.github/workflows/cd.yml
frontend/
```

---

## BLOCKING deliverable — land this FIRST

### `src/core/security.py`

Dev 2 and Dev 3 cannot protect their routes until this exists.

Must export exactly these two FastAPI dependencies:

```python
from src.core.security import require_auth, require_role
```

#### `require_auth`
```python
async def require_auth(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> SalesAgent:
    """
    Validate RS256 JWT. Raise HTTP 401 if invalid/expired.
    Load and return the SalesAgent from DB.
    Raise HTTP 403 if agent.is_active is False.
    """
```

#### `require_role(required_role: AgentRole)`
```python
def require_role(required_role: AgentRole):
    """
    Returns a FastAPI dependency that calls require_auth then checks
    agent.role >= required_role in the hierarchy:
      READ_ONLY < AGENT < SALES_MANAGER < ADMIN
    Raise HTTP 403 if role is insufficient.
    """
```

#### JWT spec
- Algorithm: `RS256`
- Claims: `sub` (agent_id as string), `role` (AgentRole value), `exp` (Unix timestamp)
- Keys from settings: `settings.JWT_PRIVATE_KEY` (PEM), `settings.JWT_PUBLIC_KEY` (PEM)
- Library: `python-jose[cryptography]` or `PyJWT`
- Token expiry: `settings.JWT_EXPIRE_MINUTES` (default 60)

#### Auth endpoints to implement in `integrations/` or a new `auth.py`
```
POST /api/v1/auth/login     { email, password } → { access_token, token_type }
POST /api/v1/auth/refresh   { access_token }    → { access_token, token_type }
GET  /api/v1/auth/me        → SalesAgent (requires require_auth)
```

Acceptance: `require_auth` passes for valid token, raises 401 for expired, raises 403 for inactive agent.

---

## Lead routes (`src/api/v1/leads.py`)

```
POST   /api/v1/leads              create lead (require_auth)
GET    /api/v1/leads              list leads, filter by status/agent (require_auth)
GET    /api/v1/leads/{id}         get lead detail (require_auth)
PATCH  /api/v1/leads/{id}         update status / assignment (require_auth)
DELETE /api/v1/leads/{id}         soft-delete: set is_active=False (require_role: ADMIN)
```

DTOs in `src/application/dto/lead_dto.py`:
```python
class CreateLeadRequest(BaseModel): ...
class UpdateLeadRequest(BaseModel): ...
class LeadResponse(BaseModel): ...
class LeadListResponse(BaseModel):
    items: list[LeadResponse]
    total: int
    page: int
    page_size: int
```

---

## Fiverr webhook (`src/api/v1/integrations/`)

```
POST /api/v1/integrations/fiverr/webhook
```

On new order event:
1. Parse Fiverr webhook payload → create `LeadModel` in DB
2. Publish NATS event:
   ```python
   await event_bus.publish(
       subject="leads.created",
       event_type="lead.created.fiverr",
       payload={"lead_id": str(lead.id), "fiverr_order_id": order_id},
   )
   ```
3. Return 200

---

## `src/main.py`

Startup lifespan must call in order:
1. `await qdrant_client.ensure_collections()`
2. `await nats_client.connect()`
3. Log startup complete with structlog

Shutdown lifespan must call:
1. `await nats_client.close()`

Register all routers from `api/v1/router.py`. Mount CORS middleware.
Trusted origins from `settings.ALLOWED_ORIGINS`.

---

## Frontend (`frontend/`)

Stack: Next.js 15 (App Router) · TypeScript strict · Tailwind CSS 4.x · shadcn/ui · Zustand · SWR

### Screens to build

| Screen | File path | Key components |
|--------|-----------|---------------|
| Login | `app/login/page.tsx` | Email/password form → `POST /api/v1/auth/login` → store JWT in httpOnly cookie |
| Dashboard | `app/page.tsx` | Lead pipeline Kanban: 4 columns (NEW / CONTACTED / QUOTED / WON\|LOST) |
| Conversation | `app/leads/[id]/chat/page.tsx` | Message thread + input box + SuggestionPanel |
| Suggestion panel | `components/SuggestionPanel.tsx` | 5 cards from `GET /api/v1/suggestions/{conv_id}`, click-to-insert |
| Quotation builder | `app/leads/[id]/quotation/page.tsx` | Line items table, total, send button → `POST /api/v1/quotations/generate` |
| Resource library | `app/resources/page.tsx` | File upload + list of indexed docs |
| Admin panel | `app/admin/page.tsx` | Agent management (SALES_MANAGER/ADMIN only, guard with role check) |

### Auth flow (exact)
```typescript
// On login
const { access_token } = await postLogin(email, password)
// Store in httpOnly cookie via API route (next.js route handler), not localStorage
document.cookie = `token=${access_token}; path=/; SameSite=Strict`

// On every fetch
headers: { Authorization: `Bearer ${token}` }

// On 401 response → redirect to /login
```

### Environment variable
```
NEXT_PUBLIC_API_URL=http://localhost:8000   # dev
```
Never hard-code the API URL.

---

## CI/CD workflows

### `.github/workflows/ci.yml` (runs on every PR)
Steps in order:
```yaml
1. ruff check backend/src/
2. mypy backend/src/ --ignore-missing-imports
3. pytest backend/tests/ -x --tb=short
4. Run prompt eval: python -m pytest backend/prompts/ -k "eval_suite"
5. npm run build (frontend/)
6. npm run lint (frontend/)
```
All steps must pass. Fail fast (`-x`).

### `.github/workflows/cd.yml` (runs on merge to `main`)
Steps in order:
```yaml
1. Build backend image: docker build -f deploy/docker/app.Dockerfile -t $IMAGE_TAG .
2. Build worker image: docker build -f deploy/docker/worker.Dockerfile -t $WORKER_TAG .
3. Push both images to registry
4. kubectl apply -k deploy/k8s/
5. kubectl rollout status deployment/betopia-api
```

---

## Kubernetes (`deploy/k8s/`)

### Scaling targets
- `betopia-api`: 4 replicas, CPU 500m request / 2000m limit
- `betopia-worker-p1`: KEDA ScaledObject on Redis list `p1-high`, min=2 max=10
- `betopia-worker-p2`: KEDA ScaledObject on Redis list `p2-normal`, min=1 max=5
- `betopia-worker-p3`: KEDA ScaledObject on Redis list `p3-batch`, min=1 max=3

### `hpa.yaml`
HPA on `betopia-api`: scale at 70% CPU, min=4 max=20.

### `ingress.yaml`
Kong ingress:
- `/api/v1/` → `betopia-api:8000`
- `/` → `betopia-frontend:3000`

---

## Acceptance criteria

| Check | Pass condition |
|-------|---------------|
| Auth | Valid JWT → 200; expired JWT → 401; wrong role → 403 |
| Lead CRUD | All 5 lead endpoints return correct status codes |
| Frontend login | Login form sets token cookie; protected routes redirect if no cookie |
| Suggestion panel | 5 suggestion cards render from live API data |
| CI | All CI steps pass on a clean branch |
| Docker build | Both Dockerfiles build without error (`docker build`) |
| K8s manifests | `kubectl apply --dry-run=client -k deploy/k8s/` exits 0 |

---

## What you must NOT do

- Do not modify any files owned by Dev 1, Dev 2, or Dev 3.
- Do not add business logic to `security.py` — it must only do auth/authz.
- Do not store JWT in localStorage — httpOnly cookie only.
- Do not hard-code API keys or secrets anywhere; all must come from env vars / K8s secrets.
- Do not merge to `main` if any CI step fails.
