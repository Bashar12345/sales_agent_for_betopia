.PHONY: install dev worker migrate lint format test certs \
        vm1-up vm1-down vm1-logs vm1-build \
        vm2-up vm2-down vm2-logs vm2-build \
        vm3-up vm3-down vm3-logs vm3-build \
        vm-all-build

# ── Local development ─────────────────────────────────────────────────────────
install:
	pip install -e ".[dev]"

dev:
	uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload

worker:
	celery -A src.workers.celery_app worker --loglevel=info --concurrency=4

beat:
	celery -A src.workers.celery_app beat --loglevel=info

flower:
	celery -A src.workers.celery_app flower --port=5555

migrate:
	alembic upgrade head

migrate-new:
	alembic revision --autogenerate -m "$(msg)"

lint:
	ruff check src tests
	mypy src

format:
	ruff format src tests
	ruff check --fix src tests

test:
	pytest tests/ -v --cov=src --cov-report=term-missing

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test-evals:
	pytest tests/evals/ -v

# ── Legacy single-VM (development only) ──────────────────────────────────────
docker-up:
	docker compose -f docker-compose.server.yml up --build

docker-down:
	docker compose -f docker-compose.server.yml down

docker-logs:
	docker compose -f docker-compose.server.yml logs -f

# ── VM1: Kong + FastAPI + PostgreSQL + Redis + NATS ───────────────────────────
# Before first run: cp .env.vm1.example .env && make certs
vm1-build:
	docker compose -f docker-compose.vm1.yml build

vm1-up:
	docker compose -f docker-compose.vm1.yml up -d

vm1-down:
	docker compose -f docker-compose.vm1.yml down

vm1-logs:
	docker compose -f docker-compose.vm1.yml logs -f

vm1-restart:
	docker compose -f docker-compose.vm1.yml restart

vm1-ps:
	docker compose -f docker-compose.vm1.yml ps

# ── VM2: Celery Worker + Beat + Flower ───────────────────────────────────────
# Before first run: cp .env.vm2.example .env (fill in VM1_INTERNAL_IP, VM3_INTERNAL_IP)
vm2-build:
	docker compose -f docker-compose.vm2.yml build

vm2-up:
	docker compose -f docker-compose.vm2.yml up -d

vm2-down:
	docker compose -f docker-compose.vm2.yml down

vm2-logs:
	docker compose -f docker-compose.vm2.yml logs -f

vm2-restart:
	docker compose -f docker-compose.vm2.yml restart

vm2-ps:
	docker compose -f docker-compose.vm2.yml ps

# ── VM3: Qdrant + MinIO + Nginx ───────────────────────────────────────────────
# Before first run: cp .env.vm3.example .env
vm3-build:
	docker compose -f docker-compose.vm3.yml build

vm3-up:
	docker compose -f docker-compose.vm3.yml up -d

vm3-down:
	docker compose -f docker-compose.vm3.yml down

vm3-logs:
	docker compose -f docker-compose.vm3.yml logs -f

vm3-restart:
	docker compose -f docker-compose.vm3.yml restart

vm3-ps:
	docker compose -f docker-compose.vm3.yml ps

# ── Build all images (run on each VM separately, or in CI) ───────────────────
vm-all-build:
	docker compose -f docker-compose.vm1.yml build
	docker compose -f docker-compose.vm2.yml build

# ── Generate RS256 key pair for JWT (run once, then copy certs/ to all VMs) ──
certs:
	mkdir -p certs
	openssl genrsa -out certs/private.pem 2048
	openssl rsa -in certs/private.pem -pubout -out certs/public.pem
	chmod 600 certs/private.pem
	@echo "RS256 key pair generated in ./certs/"
	@echo "IMPORTANT: Copy ./certs/ to VM2 and VM3 as well (workers need public.pem)"

# ── Diagnostics ───────────────────────────────────────────────────────────────
shell:
	python -c "import asyncio; from src.infrastructure.db.session import engine; print('PostgreSQL connected')"

qdrant-status:
	curl -sf http://localhost:6333/collections | python3 -m json.tool

nats-status:
	curl -sf http://localhost:8222/jsz | python3 -m json.tool

minio-status:
	curl -sf http://localhost:9000/minio/health/ready && echo "MinIO OK" || echo "MinIO unreachable"

kong-status:
	curl -sf http://localhost:8000/health | python3 -m json.tool

# ── Database ──────────────────────────────────────────────────────────────────
db-backup:
	docker exec postgres pg_dump -U betopia sales_agent | gzip > backup_$(shell date +%Y%m%d_%H%M%S).sql.gz

db-restore:
	@echo "Usage: gunzip -c backup.sql.gz | docker exec -i postgres psql -U betopia sales_agent"
