# [OWNER: Dev 1 — Data Foundation (P3)]
"""Async SQLAlchemy session factory + FastAPI dependency.

Driver: asyncpg (PostgreSQL 17).
Pooling strategy:
  - Direct connection in development / CI.
  - In production, the app connects through PgBouncer (transaction mode,
    pool_size=500 configured on the PgBouncer side).  When PGBOUNCER_HOST is
    set, the DATABASE_URL includes ?prepared_statement_cache_size=0 so
    asyncpg does not use server-side prepared statements, which are
    incompatible with PgBouncer transaction mode.

Scale target: 2,000 concurrent users.
  pool_size=40, max_overflow=20 → up to 60 connections per app replica.
  With 4 replicas behind PgBouncer this stays well within pg max_connections.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.settings import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    # Pool sizing for 2,000 concurrent users (4 replicas × 60 = 240 pg connections)
    pool_size=40,
    max_overflow=20,
    pool_recycle=1800,          # recycle before PostgreSQL idle timeout
    pool_pre_ping=True,         # evict stale connections on checkout
    echo=settings.DEBUG,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise