"""Alembic env configured for async SQLAlchemy engine."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import AsyncEngine

from momdiary.config import get_settings
from momdiary.models.orm import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override the URL from env so tests can point at an ephemeral DB.
config.set_main_option("sqlalchemy.url", get_settings().momdiary_db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection, schema=None) -> None:  # type: ignore[no-untyped-def]
    # `version_table_schema` keeps Alembic's bookkeeping table in the per-test
    # schema (None in production → default `public`). The data tables follow the
    # connection's search_path, which is pinned in `run_migrations_online` via a
    # connect event — NOT with a statement here, because issuing SQL before
    # `context.begin_transaction()` opens a stray transaction that breaks the
    # transactional-DDL commit and silently rolls the whole migration back.
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=schema,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = AsyncEngine(
        engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
            future=True,
        )
    )
    # Integration tests pass a per-test schema; pin the connection's search_path
    # to it on connect (outside the migration transaction) so CREATE TABLE lands
    # in that schema. Production passes nothing → behavior unchanged.
    schema = config.attributes.get("version_table_schema")
    if schema:
        from sqlalchemy import event

        @event.listens_for(connectable.sync_engine, "connect")
        def _set_search_path(dbapi_conn, _record):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute(f'SET search_path TO "{schema}", public')
            cur.close()

    async with connectable.connect() as connection:
        await connection.run_sync(lambda c: _do_run_migrations(c, schema))
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
