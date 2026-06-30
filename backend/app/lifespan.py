"""Lifespan singletons: app DB pool, checkpointer (langgraph schema, psycopg3), store,
providers, compiled companion graph, standalone bracket graph, and the scheduler
(only when RUN_SCHEDULER). Built once, shared via app.state. (backend-plan §3.1)"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.memory import InMemoryStore
from langgraph.store.postgres.aio import AsyncPostgresStore
from sqlalchemy import text

from app.config import get_settings
from app.db.session import make_engine, make_sessionmaker
from app.graph.build import compile_graph
from app.graph.subgraphs.bracket_ops import compile_bracket_ops
from app.providers import build_providers

log = logging.getLogger("pitchiq.lifespan")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    app.state.settings = s

    # (1) App DB — asyncpg pool, `app` schema
    engine = make_engine(s)
    app.state.engine = engine
    app.state.sessionmaker = make_sessionmaker(engine)

    # ensure schemas exist (first run; alembic also creates them)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS app"))
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS langgraph"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
    except Exception as e:  # noqa: BLE001
        log.warning("schema bootstrap skipped: %s", e)

    # (2) Checkpointer — psycopg3 pool, langgraph schema (search_path in the URL)
    app.state._cp_cm = None
    app.state._store_cm = None
    checkpointer: Any = None
    store: Any = None
    try:
        cp_cm = AsyncPostgresSaver.from_conn_string(s.CHECKPOINTER_DB_URL)
        checkpointer = await cp_cm.__aenter__()
        await checkpointer.setup()
        app.state._cp_cm = cp_cm
    except Exception as e:  # noqa: BLE001
        log.warning("AsyncPostgresSaver unavailable, falling back to memory: %s", e)
        from langgraph.checkpoint.memory import InMemorySaver

        checkpointer = InMemorySaver()
    app.state.checkpointer = checkpointer

    # (3) Long-term Store
    if s.ENV == "prod":
        try:
            store_cm = AsyncPostgresStore.from_conn_string(s.CHECKPOINTER_DB_URL)
            store = await store_cm.__aenter__()
            await store.setup()
            app.state._store_cm = store_cm
        except Exception as e:  # noqa: BLE001
            log.warning("AsyncPostgresStore unavailable, using InMemoryStore: %s", e)
            store = InMemoryStore()
    else:
        store = InMemoryStore()
    app.state.store = store

    # (4) Providers
    app.state.providers = build_providers(s)

    # (5) Compiled graphs
    app.state.graph = compile_graph(checkpointer=checkpointer, store=store)
    app.state.bracket_graph = compile_bracket_ops(checkpointer=checkpointer)

    # (6) Scheduler — ONLY on the worker replica
    app.state.scheduler = None
    if s.RUN_SCHEDULER:
        try:
            from app.scheduler.jobs import init_jobs, nightly_sync, poll_live, schedule_briefings
            from app.scheduler.scheduler import build_scheduler

            scheduler = build_scheduler(s)
            init_jobs(
                sessionmaker=app.state.sessionmaker,
                providers=app.state.providers,
                settings=s,
                scheduler=scheduler,
            )
            scheduler.add_job(poll_live, "interval", seconds=s.LIVE_POLL_SECONDS, id="poll_live", max_instances=1, replace_existing=True)
            scheduler.add_job(nightly_sync, "cron", hour=3, id="nightly_sync", replace_existing=True)
            scheduler.start()
            await schedule_briefings()
            app.state.scheduler = scheduler
            log.info("scheduler started")
        except Exception as e:  # noqa: BLE001
            log.warning("scheduler failed to start: %s", e)

    try:
        yield
    finally:
        if app.state.scheduler:
            app.state.scheduler.shutdown(wait=False)
        if app.state._store_cm:
            await app.state._store_cm.__aexit__(None, None, None)
        if app.state._cp_cm:
            await app.state._cp_cm.__aexit__(None, None, None)
        await engine.dispose()
