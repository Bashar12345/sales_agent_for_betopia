# ─────────────────────────────────────────────────────────────────────────────
# Sales Intelligence Agent — Celery Worker Image
# Target: VM2 (connects to Redis/NATS on VM1, Qdrant/MinIO on VM3)
# Python 3.12-slim multi-stage
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    libmupdf-dev \
    mupdf-tools \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -e "." --prefix=/install

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libssl3 \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r worker && useradd -r -g worker -d /app worker

COPY --from=builder /install /usr/local

COPY --chown=worker:worker src/        /app/src/
COPY --chown=worker:worker prompts/    /app/prompts/
COPY --chown=worker:worker certs/      /app/certs/
COPY --chown=worker:worker pyproject.toml /app/

RUN mkdir -p /tmp/quotations /tmp/proposals \
    && chown -R worker:worker /tmp/quotations /tmp/proposals

USER worker

# No port — workers pull tasks from Redis broker
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD celery -A src.workers.celery_app inspect ping || exit 1

# concurrency=4: tune per VM2 CPU count
# prefetch-multiplier=1: fair dispatch for slow LLM tasks (set in celery_app.py too)
CMD ["celery", "-A", "src.workers.celery_app", "worker", \
     "--loglevel=info", \
     "--concurrency=4", \
     "--max-tasks-per-child=100"]
