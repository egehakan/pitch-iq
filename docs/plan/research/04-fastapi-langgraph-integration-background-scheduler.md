# Research: FastAPI ⇄ LangGraph integration + background scheduler

> Cited synthesis from the Pitch IQ research workflow (run 2026-06-30). Versions/URLs are primary-source-verified; see open questions for unresolved items.

**Executive summary:** As of late June 2026 the current stack is FastAPI 0.138.2, Starlette 1.3.1, Uvicorn 0.49.0, langgraph 1.2.7, and langgraph-checkpoint-postgres 3.1.0. The biggest change for SSE is that FastAPI now ships a first-party EventSourceResponse and ServerSentEvent in fastapi.sse (added in 0.135.0, PR #15030), which sets text/event-stream, Cache-Control: no-cache, X-Accel-Buffering: no, sends a keep-alive ping every ~15s, and handles disconnects/Last-Event-ID for you — so for new code on FastAPI ≥0.135 it is the recommended path over hand-rolled StreamingResponse, with sse-starlette 3.4.5 as the cross-version fallback. Shared resources (compiled graph, AsyncPostgresSaver, DB pool) should be created once in a lifespan async context manager and accessed via Depends; AsyncPostgresSaver needs .setup() once and, for manual connections, autocommit=True and row_factory=dict_row. For an MVP, a lightweight custom JWT dependency (PyJWT + pwdlib[argon2], HS256, OAuth2PasswordBearer) is simpler and more future-proof than fastapi-users 15.0.5, which is now in maintenance mode. For the per-fixture briefing scheduler, APScheduler 3.11.3 (AsyncIOScheduler + a persistent SQLAlchemyJobStore on the same Postgres) is the recommended MVP choice: async-native, in-process, durable one-off 'date' jobs, no extra broker. Note APScheduler 4.x is still alpha (4.0.0a6) and arq 0.28.0 is in maintenance-only mode, while Celery 5.6.3 is heavier (broker + separate worker/beat, no native asyncio).

---

## FastAPI ⇄ LangGraph integration + background scheduler (verified 2026-06-30)

### Pinned versions

| Package | Version | Released | Source |
|---|---|---|---|
| FastAPI | **0.138.2** | 2026-06-29 | [pypi](https://pypi.org/project/fastapi/) |
| Starlette | **1.3.1** | 2026-06-12 | [pypi](https://pypi.org/project/starlette/) |
| Uvicorn | **0.49.0** | 2026-06-03 | [pypi](https://pypi.org/project/uvicorn/) |
| sse-starlette | **3.4.5** | 2026-06-20 | [pypi](https://pypi.org/project/sse-starlette/) |
| langgraph | **1.2.7** | — | [pypi json](https://pypi.org/pypi/langgraph/json) |
| langgraph-checkpoint-postgres | **3.1.0** | 2026-05-12 | [pypi](https://pypi.org/project/langgraph-checkpoint-postgres/) |
| APScheduler | **3.11.3** (4.0.0a6 alpha) | 2026-06-28 | [pypi](https://pypi.org/project/APScheduler/) |
| Celery | **5.6.3** | 2026-03-26 | [pypi](https://pypi.org/project/celery/) |
| arq | **0.28.0** (maintenance-only) | 2026-04-16 | [pypi](https://pypi.org/project/arq/) |
| fastapi-users | **15.0.5** (maintenance mode) | 2026-03-27 | [pypi](https://pypi.org/project/fastapi-users/) |

### Server-Sent Events: prefer FastAPI's built-in EventSourceResponse

The headline change since early 2026 is that **FastAPI ships first-party SSE**. As of **0.135.0** (PR #15030, [commit 2238155](https://github.com/fastapi/fastapi/commit/22381558446c5d1ac376680a6581dd63b3a04119)) you import from `fastapi.sse`:

```python
from fastapi.sse import EventSourceResponse, ServerSentEvent
```

It is documented in the official [Server-Sent Events tutorial](https://fastapi.tiangolo.com/tutorial/server-sent-events/). The response sets the correct **`text/event-stream`** media type, plus **`Cache-Control: no-cache`** and **`X-Accel-Buffering: no`** (the header that stops Nginx/proxy buffering of the stream), and sends a keep-alive **ping comment every ~15s** so idle connections aren't dropped. It also understands the `Last-Event-ID` reconnection header. Because the framework owns disconnect handling here, you generally don't need to poll `request.is_disconnected()` yourself.

Pattern for a path operation:

```python
from fastapi.sse import EventSourceResponse, ServerSentEvent

@app.get("/chat", response_class=EventSourceResponse)
async def chat(req: ChatIn, request: Request, app_state=Depends(get_state)):
    async def gen():
        async for chunk in app_state.graph.astream(
            {"messages": [("user", req.text)]},
            config={"configurable": {"thread_id": req.thread_id}},
            stream_mode="messages",
        ):
            msg, metadata = chunk            # (message_chunk, metadata)
            if metadata.get("langgraph_node") == "agent" and msg.content:
                yield ServerSentEvent(data=msg.content, event="token")
        yield ServerSentEvent(event="done", data="[DONE]")
    return EventSourceResponse(gen())
```

LangGraph's streaming contract is documented [here](https://docs.langchain.com/oss/python/langgraph/streaming): `astream(..., stream_mode="messages")` yields `(message_chunk, metadata)` for token output; `astream_events(version="v2")` gives finer events (filter `on_chat_model_stream`). On **Python <3.11** you must pass `RunnableConfig` explicitly into async LLM calls for token streaming to work. `streaming=True` on the chat model is required.

**When to use sse-starlette / StreamingResponse instead:** if you're pinned below FastAPI 0.135, use [sse-starlette](https://github.com/sysid/sse-starlette) 3.4.5's `EventSourceResponse` (same semantics). A raw `StreamingResponse(gen(), media_type="text/event-stream")` still works but you must set `Cache-Control`/`X-Accel-Buffering` yourself and check `await request.is_disconnected()` inside the loop to stop generation when the client leaves. Also disable proxy buffering at the edge (Nginx `proxy_buffering off;`).

### Lifespan, DI, and a shared compiled graph + AsyncPostgresSaver

Use the `lifespan` async context manager — the official replacement for the deprecated `@app.on_event` ([docs](https://fastapi.tiangolo.com/advanced/events/)) — to build expensive singletons once and share them across requests via `Depends`:

```python
from contextlib import asynccontextmanager
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer:
        await checkpointer.setup()          # idempotent; first run creates tables
        app.state.graph = build_graph().compile(checkpointer=checkpointer)
        yield
        # context manager tears the pool down on shutdown

def get_state(request: Request):
    return request.app.state
```

`AsyncPostgresSaver` lives in `langgraph.checkpoint.postgres.aio` and `.from_conn_string()` is an async context manager ([checkpoint-postgres README](https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/README.md)). Call `.setup()` once. If you instead manage a long-lived psycopg `AsyncConnectionPool`, you **must** create connections with `autocommit=True` and `row_factory=dict_row`, or checkpoint operations raise `TypeError: tuple indices must be integers...`. The compiled graph is thread-safe to reuse; per-conversation state is isolated by `thread_id` in the config, so one compiled graph + one saver serves all requests.

### Auth for an MVP

Recommend a **lightweight custom JWT dependency** over a framework. FastAPI's own [OAuth2-JWT tutorial](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) now uses **PyJWT** (`pip install pyjwt`) and **pwdlib with Argon2** (`pip install "pwdlib[argon2]"`), HS256, an `OAuth2PasswordBearer` scheme, and a `get_current_user` dependency that decodes the token and raises 401 on `InvalidTokenError`. This is ~40 lines, no extra moving parts, and production-reasonable. [fastapi-users 15.0.5](https://pypi.org/project/fastapi-users/) still works and gives you registration/verification/OAuth out of the box, but it is **in maintenance mode** (security/deps only; a successor toolkit is planned), so for greenfield MVP code the custom dependency is the simpler, lower-risk default. Reach for fastapi-users only if you need its full user-management surface immediately.

### Background scheduler: APScheduler vs Celery vs arq

| | Async fit | Durability | Cron / interval / one-off | Coexistence | Op weight |
|---|---|---|---|---|---|
| **APScheduler 3.11.3** | `AsyncIOScheduler` (native asyncio) | Persistent jobstores: SQLAlchemy(Postgres), Redis, Mongo | All three; `'date'` trigger for one-off | **In-process** (start in lifespan) | Lowest — no broker |
| **Celery 5.6.3** | No native asyncio (prefork/eventlet/gevent) | Broker + result backend | Beat for periodic; ETA/countdown for one-off | **Separate worker + beat** process | Highest |
| **arq 0.28.0** | Native asyncio | Redis-backed, pessimistic | `cron()`; `_defer_until`/`_defer_by` for one-off | **Separate worker** process | Medium (needs Redis) |

Sources: APScheduler [user guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html) and [PyPI](https://pypi.org/project/APScheduler/); Celery [PyPI](https://pypi.org/project/celery/); arq [GitHub](https://github.com/python-arq/arq) and [docs](https://arq-docs.helpmanual.io/).

**Recommendation: APScheduler 3.11.3 with `AsyncIOScheduler` + a persistent `SQLAlchemyJobStore` on the same Postgres.** The briefing requirement is "one job per upcoming fixture," i.e. **one-off jobs at a specific datetime** (e.g. kickoff minus N hours) — APScheduler's `'date'` trigger fits exactly:

```python
scheduler.add_job(generate_briefing, "date", run_date=kickoff - timedelta(hours=2),
                  args=[fixture_id], id=f"briefing:{fixture_id}", replace_existing=True)
```

It runs **in-process**, started from the FastAPI lifespan, so no broker and no extra deployment unit; it reuses the Postgres you already run for the checkpointer; jobs in the persistent store **survive restarts** (note: you must set an explicit `id` + `replace_existing=True` or you get duplicate jobs on each boot). Two caveats: (1) APScheduler **4.x is still alpha** (`4.0.0a6`, no new alpha since 2025) — stay on 3.x for production; (2) running the scheduler in-process with **multiple Uvicorn workers** causes duplicate firings — for the MVP run a single web process, or split the scheduler into its own one-replica process that shares the Postgres jobstore.

Pick **arq** only if you already run Redis and want decoupled async workers — but note it's **maintenance-only**. Pick **Celery** only when you need mature, heavy distributed task processing with retries/routing; for this MVP it's over-engineered and lacks native asyncio.

### Recommendations summary
- SSE: FastAPI built-in `fastapi.sse.EventSourceResponse` (≥0.135); sse-starlette 3.4.5 as fallback.
- Streaming: LangGraph `astream(stream_mode="messages")`; pass `RunnableConfig` on Py<3.11.
- Singletons: build compiled graph + `AsyncPostgresSaver` in `lifespan`; `.setup()` once; `autocommit=True`, `row_factory=dict_row`.
- Auth: custom PyJWT + `pwdlib[argon2]` dependency (HS256).
- Scheduler: APScheduler 3.11.3 `AsyncIOScheduler` + persistent Postgres jobstore, in-process, single web process.

---

### Open questions from this stream

- The exact lifespan code for AsyncPostgresSaver backed by a long-lived psycopg AsyncConnectionPool (rather than the short-lived from_conn_string context manager) was assembled from the checkpoint-postgres README facts (autocommit=True, row_factory=dict_row, .setup() once) rather than quoted from one canonical primary example; validate the pool wiring against the langgraph-checkpoint-postgres source before relying on it.
- Running APScheduler in-process with multiple Uvicorn workers will schedule/fire duplicate jobs; the single-process vs dedicated-scheduler-process deployment choice (or a leader/lock) was not pinned to a primary doc and should be confirmed for your deployment topology.
- arq 0.28.0 is maintenance-only; a maintained async alternative (e.g. saq) was seen in search results but not researched in depth — evaluate if you want an async Redis queue with active maintenance.
- LangGraph 1.2 introduced an 'event streaming / typed-projection' API alongside astream_events(v2); the precise deprecation/migration status of astream_events vs the new API was referenced in docs summaries but not confirmed from a versioned changelog.
- Celery's native asyncio support remains a work-in-progress (only third-party/pre-release shims like celery-asyncio 6.0.0a2 exist); no firm GA date was found.
- The claim that FastAPI's built-in EventSourceResponse does Pydantic serialization 'on the Rust side' appeared in a search snippet but was not confirmed in the commit/tutorial; treat the performance characterization as unverified.