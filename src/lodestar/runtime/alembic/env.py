"""Alembic environment configuration for Lodestar runtime database."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from lodestar.runtime.models import Base

# Alembic Config object
config = context.config

# Set up logging from the config file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support
target_metadata = Base.metadata


def get_url() -> str:
    """Get database URL from environment or config.

    Priority:
    1. LODESTAR_RUNTIME_DB_URL environment variable
    2. Dynamic path based on find_lodestar_root()
    3. Config file sqlalchemy.url value
    """
    # Check for explicit URL in environment
    url = os.environ.get("LODESTAR_RUNTIME_DB_URL")
    if url:
        return url

    # Try to find lodestar root and use runtime.sqlite
    try:
        from lodestar.util.paths import find_lodestar_root, get_runtime_db_path

        root = find_lodestar_root()
        if root:
            db_path = get_runtime_db_path(root)
            return f"sqlite:///{db_path}"
    except ImportError:
        pass

    # Fall back to config file value
    return config.get_main_option("sqlalchemy.url", "sqlite:///.lodestar/runtime.sqlite")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This generates SQL without connecting to the database.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates a connection and runs migrations within a transaction.
    """
    url = get_url()

    connectable = create_engine(
        url,
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
