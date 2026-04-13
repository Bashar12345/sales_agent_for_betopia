"""Alembic environment — runs migrations against the PostgreSQL database.

DATABASE_URL_SYNC is read from src/core/settings.py at runtime.
All ORM models are imported here so that Base.metadata reflects the
full schema (required for autogenerate to work correctly).
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Make the `backend/` directory importable as the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.core.settings import settings  # noqa: E402
from src.infrastructure.db.base import Base  # noqa: E402

# ── Import all ORM models so their tables appear in Base.metadata ─────────────
import src.infrastructure.db.models.sales_agent_model  # noqa: F401, E402
import src.infrastructure.db.models.lead_model  # noqa: F401, E402
import src.infrastructure.db.models.conversation_model  # noqa: F401, E402
import src.infrastructure.db.models.quotation_model  # noqa: F401, E402
import src.infrastructure.db.models.resource_model  # noqa: F401, E402
import src.infrastructure.db.models.suggestion_model  # noqa: F401, E402

# ─────────────────────────────────────────────────────────────────────────────

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emits SQL to stdout, no live DB needed."""
    url = settings.DATABASE_URL_SYNC
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects to the real PostgreSQL database."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.DATABASE_URL_SYNC

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
