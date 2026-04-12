from functools import lru_cache
from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME: str = "Sales Intelligence Agent"
    APP_ENV: str = "development"   # development | staging | production
    DEBUG: bool = False

    # ── PostgreSQL 17 ─────────────────────────────────────────────────────────
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "betopia"
    POSTGRES_PASSWORD: str = "betopia_secret"
    POSTGRES_DB: str = "sales_agent"

    # PgBouncer pooled endpoint (production); falls back to direct if empty
    PGBOUNCER_HOST: str = ""
    PGBOUNCER_PORT: int = 6432

    @computed_field  # type: ignore[misc]
    @property
    def DATABASE_URL(self) -> str:
        """Async URL for SQLAlchemy (asyncpg driver).

        Uses PgBouncer endpoint in production when PGBOUNCER_HOST is set.
        PgBouncer runs in transaction mode, so statement_cache_size=0.
        """
        host = self.PGBOUNCER_HOST or self.POSTGRES_HOST
        port = self.PGBOUNCER_PORT if self.PGBOUNCER_HOST else self.POSTGRES_PORT
        base = (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{host}:{port}/{self.POSTGRES_DB}"
        )
        # Disable asyncpg prepared-statement cache when using PgBouncer
        if self.PGBOUNCER_HOST:
            return base + "?prepared_statement_cache_size=0"
        return base

    @computed_field  # type: ignore[misc]
    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Synchronous URL for Alembic migrations (psycopg2 driver)."""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Qdrant Vector DB ──────────────────────────────────────────────────────
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str = ""                    # empty for local dev

    # The three production collections (HNSW + scalar quantisation)
    QDRANT_COLLECTION_CONVERSATIONS: str = "conversations"
    QDRANT_COLLECTION_REQUIREMENTS: str = "requirements"
    QDRANT_COLLECTION_PRICING: str = "pricing"

    # HNSW tuning — m=16, ef_construct=200 gives good recall/speed balance
    QDRANT_HNSW_M: int = 16
    QDRANT_HNSW_EF_CONSTRUCT: int = 200

    # ── LLM — Primary (OpenAI) ────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    LLM_PRIMARY_MODEL: str = "gpt-4.1"         # P1 generation + P2 Vision
    LLM_MINI_MODEL: str = "gpt-4.1-mini"       # Simple classification

    # text-embedding-3-large → 3072-dimensional vectors
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIMENSIONS: int = 3072

    # ── LLM — Fallback (Anthropic Claude) ────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    LLM_FALLBACK_MODEL: str = "claude-sonnet-4-6"  # triggers when GPT-4.1 >3s

    # Timeout thresholds for fallback chain (seconds)
    LLM_PRIMARY_TIMEOUT: float = 3.0
    LLM_FALLBACK_TIMEOUT: float = 8.0

    # ── LLM — In-house vLLM ───────────────────────────────────────────────────
    VLLM_BASE_URL: str = "http://localhost:8080"
    VLLM_MODEL: str = "mistral-7b-instruct"    # intent + tone validation

    # ── P1 suggestion configuration ───────────────────────────────────────────
    SUGGESTION_COUNT: int = 5
    INTENT_CLASSES: list[str] = [
        "new_inquiry", "follow_up", "clarification",
        "negotiation", "angry", "urgent",
    ]

    # ── Fiverr (profile reference — NO webhook) ───────────────────────────────
    FIVERR_PROFILE_ID: str = ""

    # ── JWT — RS256 asymmetric ────────────────────────────────────────────────
    JWT_RS256_PRIVATE_KEY_PATH: str = "./certs/private.pem"
    JWT_RS256_PUBLIC_KEY_PATH: str = "./certs/public.pem"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    @computed_field  # type: ignore[misc]
    @property
    def JWT_PRIVATE_KEY(self) -> str:
        path = Path(self.JWT_RS256_PRIVATE_KEY_PATH)
        if path.exists():
            return path.read_text()
        return ""

    @computed_field  # type: ignore[misc]
    @property
    def JWT_PUBLIC_KEY(self) -> str:
        path = Path(self.JWT_RS256_PUBLIC_KEY_PATH)
        if path.exists():
            return path.read_text()
        return ""

    # ── Odoo ERP Integration (future) ─────────────────────────────────────────
    ODOO_URL: str = ""
    ODOO_DB: str = ""
    ODOO_USERNAME: str = ""
    ODOO_API_KEY: str = ""

    # ── Redis 7.4+ ────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_SUGGESTION_CACHE_TTL: int = 300      # 5 min — P1 suggestion cache
    REDIS_EMBEDDING_CACHE_TTL: int = 86400     # 24 h  — embedding cache

    # ── NATS JetStream ────────────────────────────────────────────────────────
    NATS_URL: str = "nats://localhost:4222"
    NATS_STREAM_NAME: str = "sales_agent"
    NATS_SUBJECT_PREFIX: str = "betopia.sales"

    # ── Document output ───────────────────────────────────────────────────────
    DOC_OUTPUT_DIR: str = "/tmp/quotations"
    PROPOSAL_OUTPUT_DIR: str = "/tmp/proposals"

    # ── Prompts directory (Prompt-as-Code) ────────────────────────────────────
    PROMPTS_DIR: str = "./prompts"

    model_config = {"env_file": ".env", "case_sensitive": True}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
