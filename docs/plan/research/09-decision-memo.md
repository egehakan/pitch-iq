# Pitch IQ — Cross-Cutting Architecture Decision Memo
**Date:** 2026-06-30 · **Status:** Locked (single source of truth) · **Author:** Lead Architect

This memo reconciles the per-stream research with the adversarial verification verdicts. **Where a verdict corrects a research recommendation, the corrected fact is used and flagged with ⚠️ CORRECTED.**

---

## 1. Locked Stack Table

### Python (backend)

| Component | Pinned version | Source | Notes / confidence |
|---|---|---|---|
| langgraph | **1.2.7** | [pypi.org/pypi/langgraph/json](https://pypi.org/pypi/langgraph/json) | ✅ Verified (PyPI + [GitHub releases](https://github.com/langchain-ai/langgraph/releases), 2026-06-30). The observability stream's "1.2.6" is **stale → 1.2.7 wins.** |
| langchain | **1.3.11** | [pypi.org/pypi/langchain/json](https://pypi.org/pypi/langchain/json) | Hosts new `langchain.agents.create_agent`. |
| langchain-core | **1.4.8** | [pypi.org/pypi/langchain-core/json](https://pypi.org/pypi/langchain-core/json) | Satisfies langgraph `>=1.4.7,<2`. |
| langchain-openai | **1.3.3** | [pypi.org/pypi/langchain-openai/json](https://pypi.org/pypi/langchain-openai/json) | Pulls `openai>=2.26.0,<3`. |
| langgraph-checkpoint | **4.1.1** | [pypi.org/project/langgraph-checkpoint](https://pypi.org/project/langgraph-checkpoint/) | Base savers + `BaseStore`. |
| langgraph-checkpoint-postgres | **3.1.0** | [pypi.org/project/langgraph-checkpoint-postgres](https://pypi.org/project/langgraph-checkpoint-postgres/) | Prod checkpointer; uses psycopg3. |
| langgraph-prebuilt | **1.1.0** | [pypi.org/pypi/langgraph-prebuilt/json](https://pypi.org/pypi/langgraph-prebuilt/json) | `ToolNode`; `create_react_agent` deprecated. |
| langgraph-sdk | **0.4.2** | [pypi.org/pypi/langgraph-sdk/json](https://pypi.org/pypi/langgraph-sdk/json) | Resolved by core. |
| fastapi | **0.138.2** | [pypi.org/project/fastapi](https://pypi.org/project/fastapi/) | Released 2026-06-29. |
| starlette | **1.3.1** | [pypi.org/project/starlette](https://pypi.org/project/starlette/) | — |
| uvicorn | **0.49.0** | [pypi.org/project/uvicorn](https://pypi.org/project/uvicorn/) | — |
| sse-starlette | **3.4.5** | [pypi.org/project/sse-starlette](https://pypi.org/project/sse-starlette/) | ✅ Primary SSE shim (see §4). |
| **APScheduler** | **3.11.3** | [pypi.org/project/APScheduler](https://pypi.org/project/APScheduler/) | ⚠️ CORRECTED: NOT 4.x (alpha). See §3. |
| SQLAlchemy | **2.0.51** | [pypi.org/project/SQLAlchemy](https://pypi.org/project/SQLAlchemy/) | Do **not** adopt 2.1 (beta `2.1.0b3`). |
| asyncpg | **0.31.0** | [pypi.org/project/asyncpg](https://pypi.org/project/asyncpg/) | App ORM driver. |
| psycopg (psycopg3) | **3.3.4** | [pypi.org/project/psycopg](https://pypi.org/project/psycopg/) | Checkpointer driver only. |
| alembic | **1.18.5** | [pypi.org/project/alembic](https://pypi.org/project/alembic/) | Async template (`init -t async`). |
| PyJWT + pwdlib[argon2] | latest | [FastAPI security tutorial](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) | ⚠️ exact versions UNPINNED — pin in lockfile. fastapi-users (15.0.5) avoided (maintenance mode). |
| langsmith | **0.9.3** | [pypi.org/project/langsmith](https://pypi.org/project/langsmith/) | Tracing + `[pytest]` evals. |
| openevals | **0.2.0** | [pypi.org/project/openevals](https://pypi.org/project/openevals/) | Groundedness judges. |
| agentevals | **0.0.9** | [pypi.org/project/agentevals](https://pypi.org/project/agentevals/) | ⚠️ UNCERTAIN — release date looks stale (2025-07-24); confirm before pinning. |
| **Sports provider SDK** | **none (REST only)** | — | API-Football/The Odds API are plain REST + header/query auth. No official Python SDK adopted. |

### JavaScript (frontend)

| Component | Pinned version | Source | Notes / confidence |
|---|---|---|---|
| next | **16.2.9** | [registry.npmjs.org/next/latest](https://registry.npmjs.org/next/latest) | ✅ Verified (npm + [GitHub release](https://api.github.com/repos/vercel/next.js/releases/latest)). App Router, Turbopack default. |
| react / react-dom | **19.2.7** | [registry.npmjs.org/react/latest](https://registry.npmjs.org/react/latest) | ✅ Verified ([react.dev/versions](https://react.dev/versions) line 19.2). |
| ai (Vercel AI SDK) | **7.0.8** | [registry.npmjs.org/ai/latest](https://registry.npmjs.org/ai/latest) | ✅ Verified, published 2026-06-30. |
| @ai-sdk/react | **4.0.9** | [registry.npmjs.org/@ai-sdk/react/latest](https://registry.npmjs.org/@ai-sdk/react/latest) | ⚠️ UNCERTAIN — exact pairing with `ai@7.0.8` not confirmed by primary source; verify peer range in `package.json` at install. |
| @tanstack/react-query | **5.101.2** | [registry.npmjs.org/@tanstack/react-query/latest](https://registry.npmjs.org/@tanstack/react-query/latest) | — |
| tailwindcss | **4.3.2** | [registry.npmjs.org/tailwindcss/latest](https://registry.npmjs.org/tailwindcss/latest) | ✅ Verified (v4 line, [GitHub release](https://api.github.com/repos/tailwindlabs/tailwindcss/releases/latest) 2026-06-29). |
| shadcn (CLI) | **4.12.0** | [registry.npmjs.org/shadcn/latest](https://registry.npmjs.org/shadcn/latest) | ⚠️ CORRECTED: verdict pins exact **4.12.0** (research said only "CLI v4"). Tailwind-v4 + React-19 native ([docs](https://ui.shadcn.com/docs/tailwind-v4)). |

---

## 2. Sports Data Provider

### Decision
- **Primary (fixtures / live / lineups / events / standings):** **API-Football (API-SPORTS v3)** — base `https://v3.football.api-sports.io`, auth header `x-apisports-key`. WC 2026 = **`league=1`, `season=2026`**.
- **Fallback (zero-cost fixtures/results/standings):** **football-data.org v4** — competition code `WC`, header `X-Auth-Token`.
- **Odds / win-probability (prediction critic):** **The Odds API v4** — sport key `soccer_fifa_world_cup`, `apiKey` query param.

### Decisive reasons
- API-Football is the only evaluated provider with **full live match state + lineups + 12-group standings from one REST API**, cheap entry tiers, and current-season coverage on free. ✅ Verified end-to-end against the [WC2026 guide](https://www.api-football.com/news/post/fifa-world-cup-2026-guide-to-using-data-with-api-sports) and [pricing](https://www.api-football.com/pricing): `/fixtures?live=all` + `/fixtures/events` refresh ~every 15s; `/standings?league=1&season=2026` returns all 12 groups; coverage flags `events/lineups/standings = true`. As of today the group stage finished Jun 27 and the **Round of 32 is live**, so data is actively flowing.
- The Odds API gives 3-way decimal prices from 50+ books incl. sharp **Pinnacle**; derive no-vig probabilities `p_i = (1/d_i)/Σ(1/d_j)`. Pricing free 500 credits/mo, then **$30/mo for 20k credits** ([the-odds-api.com](https://the-odds-api.com/sports/fifa-world-cup-odds.html)). **Sportradar is DEFERRED** — B2B-only, ~$10k+/mo (third-party estimate), and its T&C [§2.1](https://developer.sportradar.com/sportradar-updates/page/terms-and-conditions) prohibits use "for any prediction market…financial product" without written consent, which plausibly implicates Pitch IQ.

### ⚠️ CORRECTED free-tier / coverage facts (verdict wins)
- API-Football free tier is **$0/mo, 100 requests/day AND a 10 requests/minute cap** (research omitted that both limits apply). WC2026 *is* technically usable on free (current season + all endpoints), **but 100/day + 10/min cannot sustain 15-second live polling** — production live use realistically needs the **Pro plan ($19/mo, 7,500 req/day)**. Treat free as prototyping/pre-match only — "near," not "on," the free tier for live.
- League id is **provider-specific**: `1` on API-Football vs **`732` (season `26618`) on Sportmonks** — and **Sportmonks free does NOT include the World Cup**, so Sportmonks is not a free fallback.
- API-Football's own docs warn coverage flags are `true` but "availability may vary from match to match, especially early in the tournament" — design for missing lineups/events on some fixtures.
- All three providers are **polling only** (no public websocket/push). football-data.org free scores are **delayed**; live needs a €12/mo add-on and lineups need the €29/mo Deep Data add-on, with required attribution.

---

## 3. Background Scheduler

### Decision: **APScheduler 3.11.3** (`AsyncIOScheduler`) with a persistent `SQLAlchemyJobStore` on the same Postgres, started from the FastAPI `lifespan`.

### ⚠️ CORRECTED (verdict wins)
The candidate framed as "APScheduler 4.x async" is **wrong for production**: 4.x is **alpha only** (`4.0.0a6`, Apr 2025) and the maintainer states "do **NOT** use this release in production" ([GitHub](https://github.com/agronholm/apscheduler)). **Async scheduling does not require 4.x** — stable **3.11.3** already ships `AsyncIOScheduler` ([PyPI](https://pypi.org/project/APScheduler/), released 2026-06-28).

### Reason
In-process, no broker, reuses Postgres, supports one-off `date` triggers ("N hours before kickoff") + cron, and durable jobstores survive restarts (use explicit `job id` + `replace_existing=True`). Rejected alternatives: **arq 0.28.0** is async but **maintenance-only**; **Celery 5.6.3** has **no native asyncio** (needs wrappers) and a broker + separate worker/beat — both heavier than an MVP needs.

> **Operational caveat (see Risk #4):** APScheduler in-process under multiple Uvicorn workers fires **duplicate jobs**. Run the scheduler in a **single dedicated process** (or guard with a Postgres advisory lock / leader election).

---

## 4. Streaming Approach

### Backend (LangGraph → SSE)
- **Token source:** Use LangGraph's **`graph.astream(..., stream_mode="messages")` with `version="v2"`** as the **stable MVP path** — yields `(message_chunk, metadata)`, filter by `metadata["langgraph_node"]`.
- ⚠️ CORRECTED: there is **no single "recommended" method**. The official docs now recommend, *for new apps*, the **event-streaming typed-projection API** introduced in **LangGraph v1.2** — `graph.astream_events(..., version="v3")` iterating `stream.messages → message.text` ([event-streaming docs](https://docs.langchain.com/oss/python/langgraph/event-streaming)). **But the v3 protocol is still beta**, so we ship on stable `stream_mode="messages"` (v2) now and gate the v3 migration behind its GA. The classic `langchain_core` `astream_events(version="v2")` is non-deprecated but lower-level — not used.
- **SSE transport:** wrap the async generator in **`sse-starlette` `EventSourceResponse` (3.4.5)** — sets `text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`, keep-alive pings, disconnect handling. *(The research-claimed first-party `fastapi.sse.EventSourceResponse` in 0.138.2 was **not adversarially verified** — see Open Questions; sse-starlette is the safe, verified choice and the documented fallback.)*

### Frontend (how Next consumes it)
- **Next.js Route Handler proxy** (`POST /api/chat` → FastAPI, pipe upstream body through). ⚠️ CORRECTED: a proxy is **NOT a reliability requirement** — `useChat` *can* consume external FastAPI SSE directly ([transport docs](https://ai-sdk.dev/docs/ai-sdk-ui/transport)). We choose the proxy anyway for **CORS elimination + secret hiding + auth injection**.
- **Client:** Vercel AI SDK **`useChat` with `TextStreamChatTransport({ api: '/api/chat' })`** for the MVP. ⚠️ CORRECTED: in AI SDK 5+ there is **no `streamProtocol` flag** — protocol is chosen by transport class. We use the **plain-text protocol** because the full UI-Message data protocol is format-sensitive and the official FastAPI data-stream example has **open, unresolved issues ([vercel/ai #7496](https://github.com/vercel/ai/issues/7496))**. Trade-off: text protocol drops tool-call/usage/finish metadata — acceptable for MVP; upgrade FastAPI to emit the **UI Message Stream** (`x-vercel-ai-ui-message-stream: v1`, `data: {JSON}` parts → `[DONE]`) + `DefaultChatTransport` only when the UI needs structured tool/status parts.
- **Non-streaming data** (bracket/fixtures/standings): **TanStack Query 5.101.2** server prefetch → `HydrationBoundary` → `refetchInterval` polling in live windows; merge live SSE into cache via `queryClient.setQueryData`.
- **Proxy hardening:** set `Cache-Control: no-cache, no-transform` + `X-Accel-Buffering: no` and return the upstream body without buffering.

---

## 5. Persistence

| Concern | Decision |
|---|---|
| **Checkpointer backend** | **`langgraph-checkpoint-postgres 3.1.0` → `AsyncPostgresSaver`** on Postgres. Call `.setup()` once. |
| **App DB / ORM** | **SQLAlchemy 2.0.51 async + asyncpg 0.31.0**, `postgresql+asyncpg://`. Migrations via **Alembic 1.18.5** async template. SQLModel 0.0.39 = optional ergonomic sugar only (no async wrappers, pins SQLAlchemy <2.1). |
| **Long-term memory** | `BaseStore` — `PostgresStore` (prod) / `InMemoryStore` (dev), attached via `compile(checkpointer=..., store=...)`. Checkpointer = short-term thread state + HIL; store = cross-thread user facts. |
| **Same instance?** | **YES — same Postgres instance, ISOLATED schema** (`langgraph`). |

### Concrete isolation rules
- The Python `AsyncPostgresSaver` constructor has **no `schema=` argument** (only the JS port does). Isolate via the connection `search_path`: `options='-c search_path=langgraph'` ([reference](https://reference.langchain.com/python/langgraph.checkpoint.postgres/aio/AsyncPostgresSaver)).
- **Run two separate pools:** checkpointer on **psycopg3** (`autocommit=True`, `row_factory=dict_row`, `prepare_threshold=0`), app ORM on **asyncpg**.
- Build graph + saver + pools **once in FastAPI `lifespan`**; share via `Depends`/`app.state`.
- Tournament schema is **config-driven** (`tournaments.format_config` + `scoring_config` as JSONB) — not WC-hardcoded. Bracket scoring = JSONB rules + per-pick `points_awarded`/`is_correct` + denormalized `brackets.total_score` for leaderboards.
- Choose **`durability="sync"`** explicitly for HIL/scoring-critical runs; enable **`EncryptedSerializer`** (`LANGGRAPH_AES_KEY`) for at-rest encryption of checkpoint blobs.
- Split to a separate instance only if checkpoint write volume contends with app OLTP.

---

## 6. Observability / Eval

- **Tracing:** **LangSmith native** (`langsmith 0.9.3`) — set `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`. Auto-instruments every LangGraph node (inputs/outputs, tool calls, tokens, latency, errors), zero code changes ([docs](https://docs.langchain.com/langsmith/trace-with-langgraph)). Free Developer tier ~5k traces/mo; Plus $39/seat/mo.
- **Evals in CI:** `pip install -U "langsmith[pytest]"`, `@pytest.mark.langsmith`, `LANGSMITH_TEST_CACHE` to avoid paying for LLM calls per commit.
  - **Router:** deterministic exact-match + macro-F1/confusion-matrix summary evaluator (force enum via OpenAI strict structured outputs).
  - **Generator–critic:** precision/recall/F1 on a labeled flag dataset + deterministic **Brier / log-loss / ECE** calibration vs the no-vig market line.
  - **Q&A groundedness:** `openevals 0.2.0` `HALLUCINATION_PROMPT` / `RAG_GROUNDEDNESS_PROMPT` via `create_llm_as_judge`, plus a deterministic number/entity-in-source check.
  - **Trajectory:** `agentevals 0.0.9` `create_trajectory_match_evaluator` (⚠️ version uncertain — see Open Questions).
- **Lock-in escape:** export OTel traces to LangSmith's `/otel`; **Langfuse (MIT, self-host)** or **Arize Phoenix** are the fallback if cost/self-hosting dominates ([blog](https://blog.langchain.com/opentelemetry-langsmith/)).
- **Pin the judge-model snapshot** in experiment metadata (⚠️ exact 2026 snapshot id unverified — Open Questions).

---

## 7. Top 8 Risks

1. **API-Football free tier too thin for live (100/day + 10/min).** → Budget the **Pro plan ($19/mo)**; poll only during live windows; cache fixtures/standings aggressively; use football-data.org as cold fallback.
2. **LangGraph v3 event-streaming is beta.** → Ship on stable `stream_mode="messages"` (v2); gate v3 migration behind GA.
3. **AI SDK full data-protocol broken for FastAPI ([#7496](https://github.com/vercel/ai/issues/7496)).** → MVP uses text protocol + `TextStreamChatTransport` behind the Next proxy; defer UI Message Stream.
4. **APScheduler fires duplicate jobs under multi-worker Uvicorn.** → Single dedicated scheduler process or Postgres advisory-lock leader election.
5. **`interrupt()` re-runs the node from its top on resume.** → Idempotent nodes, side effects *after* `interrupt()`, deterministic interrupt order, never bare-`except` around it.
6. **Checkpointer/app schema collision + psycopg misconfig.** → Isolate via `search_path=langgraph`, dedicated psycopg3 pool (`autocommit=True`, `row_factory=dict_row`, `prepare_threshold=0`), run `setup()` once.
7. **Sports/odds legal exposure (prediction-market clause, gambling).** → Avoid Sportradar; derive probabilities from The Odds API; never resell raw odds; show "18+ Gamble Responsibly" if odds are surfaced; verify football-data.org attribution/ToS before commercial use.
8. **Bleeding-edge version drift (many libs released within days of today).** → Commit exact lockfiles (`uv.lock`/`package-lock.json`), CI smoke-test the SSE endpoint + a graph `astream`, and verify peer ranges (esp. `@ai-sdk/react` ↔ `ai@7.0.8`) at install.

---

## 8. Open Questions (survived verification — need user input or a pre-build spike)

1. **`durability` default value** in langgraph 1.2.7 could not be quoted from a rendered primary doc (modes are exit/async/sync, "async" widely assumed default). Confirm against the live signature before relying on the implicit default; also confirm whether `durability=` is wired into `invoke/ainvoke` yet (issue #5741).
2. **`@ai-sdk/react` ↔ `ai@7.0.8` pairing** — `4.0.9` pinned from the `latest` dist-tag but the exact compatible pair is unconfirmed.
3. **`agentevals` currency** — `0.0.9` carries a 2025-07-24 date that looks stale vs langsmith/openevals; confirm a newer release (or whether trajectory eval folded into openevals) before pinning.
4. **OpenAI judge/generation model snapshot for 2026** — exact id (e.g. a pinned gpt-5.x / o3-mini snapshot) not verified from OpenAI's live model list.
5. **`fastapi.sse` first-party `EventSourceResponse`** (claimed added in FastAPI 0.135.0) was **not adversarially verified** — confirm the import exists in 0.138.2; otherwise sse-starlette 3.4.5 stands (already our pinned choice).
6. **football-data.org ToS** redistribution/caching limits — only attribution was confirmed (via third-party); read the actual ToS before commercial use.
7. **Sportradar** real WC-scoped pricing and whether Pitch IQ's "prediction critic" trips the prediction-market clause — needs a sales + legal call *if ever reconsidered*.
8. **`langchain.agents.create_agent` full signature** (`response_format`, `state_schema`, `context_schema`, pre/post-model hooks) not pulled from primary reference — confirm before relying.
9. **Product decisions affecting schema:** (a) briefings **personalized per-user vs shared per-fixture** (nullable `user_id`, affects unique constraints + cache hit rate); (b) whether **leagues span multiple tournaments** (season-long) vs scoped to one `tournament_id`.
10. **`EncryptedSerializer` auto-activation scope** — LangSmith/Platform only, or also self-hosted when `LANGGRAPH_AES_KEY` is set?

---
*Sources are inline-linked above; every pinned version traces to a PyPI/npm/registry or official-docs URL. Items marked ⚠️ CORRECTED reflect adversarial-verification verdicts overriding the originating research stream.*