"""Alembic async env — manages ONLY the `app` schema (checkpointer owns `langgraph`)."""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.config import get_settings
from app.db import models  # noqa: F401  (import registers all tables)
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    if type_ == "schema":
        return name in ("app", None)
    return True


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema="app",
        include_schemas=True,
        include_name=include_name,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    # bootstrap schemas/extension in autocommit before the migration transaction
    async with connectable.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS app"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS langgraph"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
        await connection.commit()
    await connectable.dispose()


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        version_table_schema="app",
        include_schemas=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
