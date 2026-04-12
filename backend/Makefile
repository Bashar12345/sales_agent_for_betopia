.PHONY: install dev worker migrate lint format test certs

install:
	pip install -e ".[dev]"

dev:
	uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

worker:
	celery -A src.workers.celery_app worker --loglevel=info --concurrency=4

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

docker-up:
	docker compose -f docker-compose.server.yml up --build

docker-down:
	docker compose -f docker-compose.server.yml down

docker-logs:
	docker compose -f docker-compose.server.yml logs -f

# Generate RS256 key pair for JWT (run once per environment)
certs:
	mkdir -p certs
	openssl genrsa -out certs/private.pem 2048
	openssl rsa -in certs/private.pem -pubout -out certs/public.pem
	@echo "RS256 key pair generated in ./certs/"
	@echo "Add to .env: JWT_RS256_PRIVATE_KEY_PATH=./certs/private.pem"

shell:
	python -c "import asyncio; from src.infrastructure.db.session import engine; print('PostgreSQL connected')"

# Check Qdrant collections
qdrant-status:
	curl -s http://localhost:6333/collections | python3 -m json.tool

# NATS stream status
nats-status:
	curl -s http://localhost:8222/jsz | python3 -m json.tool
