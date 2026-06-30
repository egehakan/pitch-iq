# Research: LangGraph — Checkpointers, Memory & Human-in-the-Loop (current state)

> Cited synthesis from the Pitch IQ research workflow (run 2026-06-30). Versions/URLs are primary-source-verified; see open questions for unresolved items.

**Executive summary:** As of 2026-06-30, LangGraph core is at 1.2.7 (Jun 30, 2026), with the persistence packages versioned independently: langgraph-checkpoint 4.1.1 (May 22, 2026), langgraph-checkpoint-postgres 3.1.0 (May 12, 2026), and langgraph-checkpoint-sqlite 3.1.0 (May 12, 2026). A checkpointer attaches at compile via builder.compile(checkpointer=...) and is keyed per conversation by config {"configurable": {"thread_id": ...}}; PostgresSaver/AsyncPostgresSaver require a one-time .setup() to create tables/indexes, and self-managed connections/pools must set autocommit=True, prepare_threshold=0, row_factory=dict_row. The recommended memory split is unchanged in concept but now first-class: a checkpointer holds short-term, thread-scoped state (conversation, HIL, time-travel, fault tolerance) while a BaseStore (InMemoryStore/PostgresStore) holds long-term, cross-thread memory (user facts/preferences), attached via compile(store=...). The current human-in-the-loop API is the interrupt() function inside a node resumed with Command(resume=...); interrupt_before/interrupt_after are now explicitly legacy debugging breakpoints, not recommended for HIL. The biggest 2025/2026 changes a new build must know: durability modes (exit/async/sync) replacing the old checkpoint_during flag; a versioned, type-safe output/streaming API (v1 __interrupt__ key → v2 GraphOutput.interrupts → v3 stream_events with .interrupts/.interrupted/.output projections); checkpoint format v3 with delta snapshots; and an EncryptedSerializer for at-rest encryption. The exact literal default durability ("async") could not be quoted from a primary page that rendered, so it is flagged.

---

## LangGraph — Checkpointers, Memory & Human-in-the-Loop (state as of 2026-06-30)

### Versions (pinned)

| Package | Version | Released | Source |
|---|---|---|---|
| `langgraph` (core) | **1.2.7** | Jun 30, 2026 | [libraries.io/pypi/langgraph](https://libraries.io/pypi/langgraph) |
| `langgraph-checkpoint` | **4.1.1** | May 22, 2026 | [pypi](https://pypi.org/project/langgraph-checkpoint/) |
| `langgraph-checkpoint-postgres` | **3.1.0** | May 12, 2026 | [pypi](https://pypi.org/project/langgraph-checkpoint-postgres/) |
| `langgraph-checkpoint-sqlite` | **3.1.0** | May 12, 2026 | [pypi](https://pypi.org/project/langgraph-checkpoint-sqlite/) |

The persistence packages version **independently** of core — `langgraph-checkpoint` (the base interfaces + serde + `InMemorySaver`/`InMemoryStore`) is at 4.x while the Postgres/SQLite backends are at 3.1.0. Pin each one. Postgres 3.1.0 shipped after a short `3.1.0a1`–`a4` prerelease run in late April–May 2026 (prior stable `3.0.5`, Mar 18, 2026), per the [PyPI release history](https://pypi.org/project/langgraph-checkpoint-postgres/).

### Checkpointers (short-term, thread-scoped)

A checkpointer is attached **at compile**: `graph = builder.compile(checkpointer=checkpointer)`, and every run is keyed by a thread: `config = {"configurable": {"thread_id": "1"}}` ([checkpointers docs](https://docs.langchain.com/oss/python/langgraph/checkpointers)). Reusing a `thread_id` resumes that conversation; a new value starts fresh. The classes:

- `InMemorySaver` (`from langgraph.checkpoint.memory import InMemorySaver`) — dev/testing, lost on restart. (`MemorySaver` remains an alias.)
- `PostgresSaver` / `AsyncPostgresSaver` — production.
- `SqliteSaver` / `AsyncSqliteSaver` — local/single-process.

**Postgres setup.** Install `pip install -U "psycopg[binary,pool]" langgraph langgraph-checkpoint-postgres`, then use the context-manager constructor and run `.setup()` once ([add-memory docs](https://docs.langchain.com/oss/python/langgraph/add-memory)):

```python
from langgraph.checkpoint.postgres import PostgresSaver
DB_URI = "postgresql://postgres:postgres@localhost:5432/postgres?sslmode=disable"
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    checkpointer.setup()          # creates tables + indexes (first run only)
    graph = builder.compile(checkpointer=checkpointer)
```

Async uses `from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver`, `async with AsyncPostgresSaver.from_conn_string(...)`, and `await checkpointer.setup()`.

**Connection/pool requirements (async and self-managed pools).** `from_conn_string` configures the connection for you, but if you pass your **own** `psycopg` connection or a `ConnectionPool`/`AsyncConnectionPool`, you must set `autocommit=True`, `prepare_threshold=0`, and `row_factory=dict_row`. `autocommit=True` is what lets `.setup()` commit its DDL and avoids prepared-statement/pipeline errors. Pattern confirmed by the [Postgres saver source](https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/langgraph/checkpoint/postgres/__init__.py) and recurring issues such as [#5327 (setup fails when autocommit is false)](https://github.com/langchain-ai/langgraph/issues/5327) and [#3193 (pipeline mode)](https://github.com/langchain-ai/langgraph/issues/3193):

```python
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
connection_kwargs = {"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row}
pool = ConnectionPool(conninfo=DB_URI, max_size=20, kwargs=connection_kwargs)
checkpointer = PostgresSaver(pool); checkpointer.setup()
```

SQLite: `SqliteSaver.from_conn_string(":memory:")` (sync) or `AsyncSqliteSaver` from `langgraph.checkpoint.sqlite.aio` ([pypi](https://pypi.org/project/langgraph-checkpoint-sqlite/)).

### Store / long-term memory vs checkpoints

The recommended split is now first-class. From the [persistence docs](https://docs.langchain.com/oss/python/langgraph/persistence): *"a checkpointer tracks the current thread, and a store tracks durable information across threads."* Use the **checkpointer for short-term** state (conversation continuity, HIL, time-travel, fault tolerance) and a **`BaseStore` for long-term, cross-thread** memory (user preferences, facts, shared knowledge). Implementations: `InMemoryStore`, `PostgresStore`/`AsyncPostgresStore` (and Redis/Oracle variants). Both are attached at compile:

```python
graph = builder.compile(checkpointer=checkpointer, store=store)
```

Inside a node you access the store via the typed runtime (`runtime: Runtime[Context]` → `runtime.store.search(namespace, query=...)` / `runtime.store.put(namespace, key, {...})`), namespaced by e.g. `("memories", user_id)`; semantic search is enabled with `index={"embed": embeddings, "dims": ...}` ([stores docs](https://docs.langchain.com/oss/python/langgraph/stores), [add-memory](https://docs.langchain.com/oss/python/langgraph/add-memory)). `PostgresStore` also requires `.setup()`.

### Human-in-the-loop: the current interrupt API

**Current primitive:** call `interrupt(payload)` inside a node (`from langgraph.types import interrupt, Command`). It persists state to the checkpointer and surfaces a JSON-serializable payload; you resume by re-invoking the graph with `Command(resume=value)`, where `value` becomes the **return value** of `interrupt()` ([interrupts docs](https://docs.langchain.com/oss/python/langgraph/interrupts)):

```python
def approval_node(state):
    approved = interrupt("Do you approve this action?")   # pauses here
    return {"approved": approved}
# resume: graph.stream_events(Command(resume=True), config=config, version="v3")
```

A checkpointer is **required**, and the resume call must reuse the same `thread_id`. On resume the node **re-executes from the top**, so: keep side effects *after* the interrupt, keep the number/order of `interrupt()` calls deterministic (resume values are matched by index), and never wrap `interrupt()` in a bare `try/except Exception` (it would swallow the interrupt). For parallel branches that interrupt simultaneously, resume with a map: `Command(resume={interrupt.id: value})`.

**Legacy/debugging:** `interrupt_before=[...]` / `interrupt_after=[...]` at `compile()` (or per-invocation) are static breakpoints. The docs are explicit: *"Static interrupts are not recommended for human-in-the-loop workflows. Use the interrupt function instead."*

**How interrupts surface when streaming (versioned output API — important 2025/26 change):**

- **v1 (default for plain `invoke`)** — interrupts appear under the `__interrupt__` key: `if "__interrupt__" in result: result["__interrupt__"][0].value`, resume with `graph.invoke(Command(resume=...), config)` ([streaming docs](https://docs.langchain.com/oss/python/langgraph/streaming)).
- **v2 (`version="v2"`)** — `graph.invoke(..., version="v2")` returns a `GraphOutput` with `.value` and `.interrupts`; `graph.stream(..., version="v2")` yields self-describing `StreamPart` dicts `{type, ns, data}` (proposal: [issue #7008](https://github.com/langchain-ai/langgraph/issues/7008)).
- **v3 (current, used throughout the 1.2 docs)** — `graph.stream_events(input, config, version="v3")` exposes typed projections: `stream.interrupted` (bool), `stream.interrupts` (`tuple[Interrupt, ...]` with `.value`/`.id`), `stream.output`, `stream.messages`, `stream.values`. Resume with `graph.stream_events(Command(resume=...), config, version="v3")`.

### Durability across process restarts

Because interrupts persist to the checkpointer, a Postgres-backed checkpointer makes HIL **durable across process restarts**: after a crash you re-attach the same `thread_id` and resume with `Command(resume=...)`. LangGraph 1.x adds **durability modes** controlling *when* checkpoints are written, passed per run (e.g. `graph.stream({...}, durability="sync")`) ([Durability type](https://reference.langchain.com/python/langgraph/types/Durability)):

- `"sync"` — persisted synchronously **before** the next step (most durable; some overhead).
- `"async"` — persisted asynchronously **while** the next step runs (balanced; small risk of a lost checkpoint on crash).
- `"exit"` — persisted **only when the graph exits** (fastest, least durable).

This replaced the older `checkpoint_during` boolean. The middle `"async"` mode is the widely-used default, but I could not quote the literal default from a doc page that rendered (see open questions); for HIL/financial steps prefer `"sync"`. Extending `durability=` to `invoke`/`ainvoke` is tracked in [issue #5741](https://github.com/langchain-ai/langgraph/issues/5741).

### Other 2025/2026 changes a new build must know

- **Checkpoint format v3** — checkpoints carry `'v': 3` with delta-encoded channel snapshots (`get_tuple` output, [checkpointers docs](https://docs.langchain.com/oss/python/langgraph/checkpointers)).
- **Serialization & encryption** — default `JsonPlusSerializer`; opt-in `EncryptedSerializer` (e.g. `from_pycryptodome_aes`, reading `LANGGRAPH_AES_KEY`) encrypts state at rest and auto-activates on LangSmith when the key is present ([checkpointers docs](https://docs.langchain.com/oss/python/langgraph/checkpointers)).
- **Typed Runtime/context** — `Runtime[Context]` + `context_schema=` is the current way to inject per-run context and reach `runtime.store` inside nodes ([add-memory](https://docs.langchain.com/oss/python/langgraph/add-memory)).
- **Conformance suite** — `langgraph-checkpoint-conformance` validates custom checkpointers.

### Recommendations (summary)

1. Pin `langgraph==1.2.7`, `langgraph-checkpoint==4.1.1`, `langgraph-checkpoint-postgres==3.1.0`, `langgraph-checkpoint-sqlite==3.1.0`.
2. Production: `PostgresSaver`/`AsyncPostgresSaver` via `from_conn_string`, call `.setup()` once; for custom pools set `autocommit=True, prepare_threshold=0, row_factory=dict_row`.
3. Use `interrupt()` + `Command(resume=...)` for HIL; treat `interrupt_before/after` as debug-only; write interrupt nodes idempotently.
4. Two-tier memory: checkpointer (short-term) + `BaseStore`/`PostgresStore` (long-term), both at `compile(...)`.
5. Stream via `stream_events(..., version="v3")` and read `.interrupts`/`.interrupted`.
6. Set `durability="sync"` for crash-critical/HIL runs; consider `EncryptedSerializer` for sensitive state.

---

### Open questions from this stream

- The literal default value of the `durability` parameter could not be quoted from a primary doc page that rendered (the durable-execution modes section did not load via fetch). The three modes least→most durable are exit/async/sync and the balanced middle mode 'async' is widely treated as the default, but a new build should confirm the default against the live durable-execution page or the stream/invoke signature before relying on it.
- Whether `durability=` is already wired into invoke/ainvoke in 1.2.7 (it was added to stream/astream first; GitHub issue #5741 tracks extending it to invoke/ainvoke). Verify on the installed version's signature.
- Relationship/stability of the two type-safe output APIs: `graph.stream(..., version="v2")`/`invoke(..., version="v2")` returning StreamPart/GraphOutput (issue #7008) versus the `graph.stream_events(..., version="v3")` typed projections used throughout the 1.2 docs — confirm which is the long-term default in your pinned version and whether v1's `__interrupt__`-in-result remains the default for plain invoke().
- Exact minimum/maximum langgraph-checkpoint version required by langgraph-checkpoint-postgres 3.1.0 (deps.dev/libraries.io metadata did not render); confirm the dependency range from the wheel metadata if strict pinning matters.
- Whether EncryptedSerializer auto-activation applies only on LangSmith/Platform or also self-hosted when LANGGRAPH_AES_KEY is set — confirm against the current checkpointers/serialization reference.