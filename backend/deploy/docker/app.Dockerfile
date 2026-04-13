# ─────────────────────────────────────────────────────────────────────────────
# Sales Intelligence Agent — FastAPI Application Image
# Target: VM1 (runs behind Kong API Gateway)
# Internal port: 8080  |  Python 3.12-slim multi-stage
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: builder — install all Python dependencies ───────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# System libs needed to build psycopg2, cryptography, PyMuPDF, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    libmupdf-dev \
    mupdf-tools \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy only the project manifest first (better layer caching)
COPY pyproject.toml .

# Install all runtime dependencies into a single prefix
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -e "." --prefix=/install

# ── Stage 2: runtime — minimal image, non-root user ──────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Runtime system libraries (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libssl3 \
    libmupdf-dev \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser && useradd -r -g appuser -d /app appuser

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY --chown=appuser:appuser src/        /app/src/
COPY --chown=appuser:appuser prompts/    /app/prompts/
COPY --chown=appuser:appuser certs/      /app/certs/
COPY --chown=appuser:appuser pyproject.toml /app/

# Pre-create output directories (MinIO handles storage; these are fallback/temp)
RUN mkdir -p /tmp/quotations /tmp/proposals \
    && chown -R appuser:appuser /tmp/quotations /tmp/proposals

USER appuser

# Internal port — Kong proxies :8000 → :8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -sf http://localhost:8080/health || exit 1

# 4 uvicorn workers — scale replicas horizontally, not workers per container
CMD ["uvicorn", "src.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "4", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--no-access-log"]
