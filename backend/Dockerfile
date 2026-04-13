# Root Dockerfile — delegates to the app image definition.
# This file exists so `docker build .` works from the backend root
# without specifying -f. Production CI uses deploy/docker/app.Dockerfile directly.
#
# Usage:
#   docker build -t sales-agent-app .
#   docker build -f deploy/docker/app.Dockerfile -t sales-agent-app .  (equivalent)

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
    curl \
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
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser && useradd -r -g appuser -d /app appuser

COPY --from=builder /install /usr/local

COPY --chown=appuser:appuser src/        /app/src/
COPY --chown=appuser:appuser prompts/    /app/prompts/
COPY --chown=appuser:appuser certs/      /app/certs/
COPY --chown=appuser:appuser pyproject.toml /app/

RUN mkdir -p /tmp/quotations /tmp/proposals \
    && chown -R appuser:appuser /tmp/quotations /tmp/proposals

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -sf http://localhost:8080/health || exit 1

CMD ["uvicorn", "src.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "4", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--no-access-log"]
