"""Alembic environment.

Runs migrations synchronously with the psycopg3 driver. The URL comes from the
`DATABASE_URL` environment variable; the async `+psycopg` marker is normalized to
a plain sync DSN so Alembic's synchronous engine can use it.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from tmdb_reminder import models  # noqa: F401  (register tables on Base.metadata)
from tmdb_reminder.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_dsn() -> str:
    dsn = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://tmdb:tmdb@localhost:5432/tmdb_reminder",
    )
    # psycopg3 speaks both sync and async; keep the +psycopg marker as-is.
    return dsn


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_dsn(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _sync_dsn()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
