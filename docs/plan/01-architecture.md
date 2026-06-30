# 01 — System Architecture

> Purpose: the authoritative wiring diagram for Pitch IQ — how the frontend, Next proxy, FastAPI, the LangGraph runtime, data providers, scheduler, Postgres, and LangSmith fit together, plus the two hot paths (chat, briefing), the deployment topology, and the canonical env/secrets surface.

**Source of truth:** [`research/canonical-spec.md`](research/canonical-spec.md) §2 (and §5–§6 for the pieces referenced here). Library/version/API claims trace to [`research/04-fastapi-langgraph-integration-background-scheduler.md`](research/04-fastapi-langgraph-integration-background-scheduler.md), [`research/06-persistence.md`](research/06-persistence.md), and [`research/09-decision-memo.md`](research/09-decision-memo.md).

**Two layers, kept strictly separate (and this whole doc is about layer a):**
- **(a) Runtime patterns** — LangGraph behavior *inside the product*. This document describes the deployed system that serves users.
- **(b) Build workflows** — Claude Code dynamic-workflow orchestration used *to build the product*. Out of scope here; see `06-workflows/` / spec §8.

This doc describes the system *boundaries* and *flows*. It deliberately does **not** duplicate:
- LangGraph node/edge internals (the 7 runtime patterns) → see `02-langgraph-design.md` / spec §3.
- The Postgres app schema (tables/columns) → see `04-backend-plan.md` / spec §5.

---

## 1. System + component diagram

Five tiers: browser → Next proxy → FastAPI (+ embedded LangGraph runtime) → external providers/observability → one Postgres with two isolated schemas. The scheduler/poller lives in a **separate process** that shares the same FastAPI image and the same Postgres (see §4).

```mermaid
flowchart TB
  subgraph Browser["Browser — Next.js 16.2.9 App Router (React 19.2.7)"]
    direction TB
    UI["/tournament/[slug] · 3-pane:<br/>ChatPanel · LivePanel · BracketBoard"]
    UC["useChat(TextStreamChatTransport '/api/chat')<br/>ai 7.0.8 · @ai-sdk/react 4.0.9"]
    TQ["TanStack Query 5.101.2<br/>(fixtures / standings / bracket cache)"]
    ES["EventSource → /api/fixtures/{id}/live<br/>(useLiveFeed)"]
  end

  subgraph NextSrv["Next.js server — Route Handlers (process 1)"]
    direction TB
    P1["app/api/chat/route.ts<br/>SSE proxy: hide BACKEND_URL,<br/>inject auth, no-transform, X-Accel-Buffering:no"]
    P2["app/api/[...path]/route.ts<br/>generic JSON proxy (auth inject, CORS-free)"]
  end

  subgraph Web["FastAPI 0.138.2 web (process 2 · scheduler OFF · scalable N)"]
    direction TB
    API["api/: chat(SSE) · auth · brackets ·<br/>leagues · briefings · tournaments · health"]
    subgraph Graph["LangGraph runtime 1.2.7 — companion_graph (app/graph/build.py)"]
      G["ingest → router →{ qa_agent | prediction |<br/>briefing | bracket_ops | chitchat } → persist_memory"]
    end
    SVC["services: poller · scoring · briefing_service"]
    LSP["lifespan singletons:<br/>compiled graph · AsyncPostgresSaver ·<br/>PostgresStore · asyncpg engine · provider clients"]
  end

  subgraph Worker["FastAPI image · RUN_SCHEDULER=true (process 3 · single replica)"]
    direction TB
    SCH["APScheduler 3.11.3 AsyncIOScheduler<br/>jobs: schedule_briefings · generate_briefing('date') ·<br/>poll_live(interval) · nightly_sync(cron)"]
    Poll["poller service (live windows only)"]
  end

  subgraph PG["Postgres (one instance — Neon / RDS)"]
    direction TB
    APPSCH["app schema<br/>(SQLAlchemy 2.0.51 + asyncpg 0.31.0)"]
    LGSCH["langgraph schema<br/>(psycopg3 3.3.4 · search_path=langgraph)<br/>checkpoints · store"]
  end

  subgraph Providers["Provider HTTP (REST polling — no push)"]
    direction TB
    AF["API-Football v3 (primary)<br/>v3.football.api-sports.io"]
    FD["football-data.org v4 (fallback)"]
    OA["The Odds API v4 (odds → win prob)"]
  end

  LS["LangSmith 0.9.3 (traces + evals)"]

  UC -->|POST /api/chat| P1
  TQ -->|JSON| P2
  ES -->|SSE| P2
  P1 -->|SSE passthrough| API
  P2 -->|HTTP + Bearer JWT| API
  API <--> Graph
  API --> SVC
  Graph -->|tools| Providers
  SVC -->|REST| Providers
  Poll -->|REST| Providers
  Graph -->|checkpointer + store| LGSCH
  API -->|ORM| APPSCH
  SVC --> APPSCH
  SCH --> APPSCH
  SCH -->|briefing subgraph headless| Graph
  Poll --> APPSCH
  Graph -.->|auto-instrument| LS
  SCH -.->|writes briefing job rows| APPSCH
```

**Component responsibilities (one line each):**

| Component | File / module | Responsibility |
|---|---|---|
| 3-pane UI | `frontend/app/tournament/[slug]/page.tsx` | Chat + live + bracket, server-prefetch → `HydrationBoundary` |
| Chat transport | `useChat(TextStreamChatTransport)` | Token stream over plain-text SSE protocol (Risk #3) |
| SSE proxy | `frontend/app/api/chat/route.ts` | Hide `BACKEND_URL`, inject auth, disable buffering |
| JSON proxy | `frontend/app/api/[...path]/route.ts` | CORS-free pass-through for all non-stream calls |
| FastAPI app | `backend/app/main.py` + `api/*` | Routers, CORS, exception handlers (RFC-9457) |
| Lifespan | `backend/app/lifespan.py` | Build graph + savers + store + pools + (scheduler if `RUN_SCHEDULER`) |
| LangGraph runtime | `backend/app/graph/build.py` | `companion_graph` compiled with checkpointer + store (internals → doc 02) |
| Services | `backend/app/services/{poller,scoring,briefing_service}.py` | Live polling, bracket scoring, headless briefing generation |
| Scheduler | `backend/app/scheduler/{scheduler,jobs}.py` | APScheduler jobs (single replica only) |
| Providers | `backend/app/providers/*` | Protocol-typed sports/odds clients + `CachingProvider` decorator |

---

## 2. The two hot paths (sequence diagrams)

### 2.1 Chat path (token streaming)

Browser → Next `/api/chat` proxy → FastAPI SSE endpoint → `graph.astream(stream_mode="messages", version="v2")` → tokens streamed back. We ship the **stable** `stream_mode="messages"` v2 contract; the typed-projection `astream_events(version="v3")` is beta and gated behind GA (Risk #2). SSE transport is **`sse-starlette` 3.4.5 `EventSourceResponse`** (chosen over the unverified first-party `fastapi.sse` — Open Question #5 in the decision memo).

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser (useChat /<br/>TextStreamChatTransport)
    participant N as Next route.ts<br/>(/api/chat proxy)
    participant F as FastAPI<br/>POST /api/chat
    participant G as companion_graph<br/>(astream messages v2)
    participant P as SportsDataProvider /<br/>OddsProvider
    participant DB as Postgres<br/>(langgraph schema)

    B->>N: POST /api/chat {message, thread_id?, tournament_id}
    N->>F: POST /api/chat (inject Bearer JWT,<br/>no-transform, X-Accel-Buffering:no)
    F->>F: get_current_user(JWT) · resolve thread_id
    F->>G: graph.astream(input, config{thread_id},<br/>stream_mode="messages", version="v2")
    G->>DB: load checkpoint (thread state)
    Note over G: ingest → router → qa_agent (ReAct)
    G->>P: tool calls (get_live_match_state, get_standings, …)
    P-->>G: Fixture / LiveMatchState / Standings (Pydantic)
    loop per (chunk, meta) where meta.langgraph_node == user-facing node
        G-->>F: AIMessageChunk token
        F-->>N: EventSourceResponse: event=token
        N-->>B: SSE token (passthrough, no buffering)
    end
    G->>DB: persist_memory → write durable facts to Store
    F-->>N: event=done [DONE]
    N-->>B: stream end → useChat renders final message
```

Notes:
- The user-facing token filter is `meta["langgraph_node"]` (only the `qa_agent` / `chitchat` node tokens reach the browser; tool chatter and internal nodes are suppressed). The MVP text protocol drops structured tool/usage parts — acceptable per Risk #3.
- TTFT target: < 1.5s p50 (spec success criteria).
- HITL bracket submit does **not** flow through this path — it runs through the brackets API (`POST /api/brackets/{id}/submit` → `{interrupt}` → `…/submit/confirm`), surfaced in the `SubmitConfirmDialog`. See doc 02 §3.4.

### 2.2 Briefing path (scheduled, headless)

A `'date'` job fires at **kickoff − `BRIEFING_LEAD_HOURS` (=2)** on the single scheduler replica → `generate_briefing(fixture_id)` → `briefing_service` runs the **briefing subgraph headless** (system `thread_id`, not a user chat) → upsert the `briefings` row → frontend later reads it via a plain JSON GET. This is decoupled from chat: nothing is streamed to a browser; the result is a stored row.

```mermaid
sequenceDiagram
    autonumber
    participant S as APScheduler<br/>'date' job (worker replica)
    participant SVC as briefing_service<br/>(app/services)
    participant BG as briefing subgraph<br/>(headless, system thread_id)
    participant P as Providers<br/>(fixture/lineups/standings/odds/h2h/form)
    participant DB as Postgres (app schema)<br/>briefings table
    participant FE as Frontend<br/>BriefingCard

    Note over S: job id briefing:{fixture_id}<br/>run_date = kickoff − BRIEFING_LEAD_HOURS
    S->>SVC: generate_briefing(fixture_id)
    SVC->>DB: upsert briefings (status=generating)
    SVC->>BG: invoke briefing subgraph (system thread_id)
    par parallel fan-out (operator.add → gathered)
        BG->>P: gather_fixture / lineups / standings
    and
        BG->>P: gather_odds / h2h / form
    end
    P-->>BG: DataFragment[] (Pydantic)
    Note over BG: plan_briefing → Send("write_section") per section<br/>→ assemble (defer fan-in)
    BG-->>SVC: Briefing(content markdown, model, thread_id)
    SVC->>DB: upsert briefings (status=ready, content, generated_at)
    Note over SVC,DB: on exception → status=failed, error set
    FE->>DB: GET /api/fixtures/{id}/briefing?type=pre_match
    DB-->>FE: BriefingOut (rendered in BriefingCard)
```

Notes:
- `briefings.status` lifecycle: `pending → generating → ready` (or `failed` with `error`). The frontend reads whatever is current; a `pending`/`generating` row renders a skeleton.
- The same briefing subgraph is **also** reachable from the chat path via route `BRIEFING` — same graph, two entry points (scheduler-headless vs. user-asked). Subgraph internals → doc 02 §3.3.
- `briefings.user_id` nullable (null = shared/generic, set = personalized) — the personalized-vs-shared product decision is Open Question #7/#9 and changes cache hit-rate, not this topology.

---

## 3. Deployment topology

Three processes, one Postgres, optional Redis later. The web tier scales horizontally; the scheduler is pinned to exactly one replica. **Hosting (Q4 resolved): Next.js on Vercel, the two FastAPI services (web + single scheduler worker) on Railway, managed Postgres (Railway Postgres or Neon).**

```mermaid
flowchart LR
  subgraph P1["Process 1 — Next.js on Vercel"]
    NX["App Router + Route Handler proxies"]
  end
  subgraph P2["Process 2 — FastAPI web (Railway)<br/>uvicorn · RUN_SCHEDULER unset<br/>(scale to N replicas)"]
    W1["web replica 1"]
    W2["web replica 2 … N"]
  end
  subgraph P3["Process 3 — scheduler/worker (Railway)<br/>same image · RUN_SCHEDULER=true<br/>EXACTLY 1 replica"]
    SC["APScheduler + poller"]
  end
  DB[("Managed Postgres — one instance<br/>(Railway/Neon)<br/>app schema + langgraph schema")]
  RD["Redis (optional, later)"]:::opt

  NX -->|server-side| W1
  NX -->|server-side| W2
  W1 --> DB
  W2 --> DB
  SC --> DB
  SC -. headless briefing subgraph .-> DB
  classDef opt stroke-dasharray: 4 4;
```

| # | Process | Image / runtime | Scaling | Scheduler | Owns |
|---|---|---|---|---|---|
| 1 | **Next.js** | Node ≥ 22 on **Vercel** | horizontal | n/a | UI + Route Handler proxies; holds `BACKEND_URL` server-only |
| 2 | **FastAPI web** | uvicorn 0.49.0, Python ≥ 3.12 on **Railway** | **horizontal (N)** | **OFF** (`RUN_SCHEDULER` unset/false) | HTTP API, SSE chat, graph `astream`, ORM reads/writes |
| 3 | **Scheduler/worker** | **same FastAPI image** on **Railway** | **single replica only** | **ON** (`RUN_SCHEDULER=true`) | APScheduler (`AsyncIOScheduler` + `SQLAlchemyJobStore` on same Postgres), poller, headless briefing runs |

**Why a single scheduler process (Risk #4):** APScheduler runs **in-process**. If it were started inside every uvicorn worker, each replica would independently fire `'date'` jobs and you would get *N* duplicate briefings per fixture. Running the scheduler in exactly one dedicated replica (or, later, a Postgres advisory-lock leader election) guarantees **one briefing per fixture**. We chose APScheduler 3.11.3 (not 4.x — alpha, "do NOT use in production") because its `AsyncIOScheduler` is async-native, in-process, needs no broker, reuses the Postgres we already run, and supports both one-off `'date'` triggers (kickoff − N h) and cron (`nightly_sync`). Durable jobs survive restarts when given an explicit `id` + `replace_existing=True`.

**Data store:** one managed Postgres serves both the app ORM (asyncpg, `app` schema) and the LangGraph checkpointer + store (psycopg3, `langgraph` schema). Two **separate connection pools**; no cross-schema FK (the `conversations.thread_id ⇄ checkpoints.thread_id` join is logical). Schema/pool details → doc 04 / spec §5. Split to a second instance only if checkpoint write volume contends with app OLTP.

**Secrets distribution:** `.env` files locally; in prod, **Vercel env vars** (frontend) and **Railway service variables** (FastAPI web + worker). Hosting is resolved (Q4: Vercel + Railway + managed Postgres); the single-scheduler invariant maps to one Railway worker service with `RUN_SCHEDULER=true`. LangSmith is configured purely via env vars; traces leave processes 2 and 3 over HTTPS.

---

## 4. Environment variables (canonical) + secrets handling

All config flows through `pydantic-settings` (`backend/app/config.py`, `Settings`) and the frontend's server-only env. The table below is the canonical set from spec §2; defaults shown where the spec pins one.

### Backend (`backend/.env.example` → `app/config.py`)

| Var | Example / default | Consumer | Secret? |
|---|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://…/pitchiq` | app ORM (asyncpg pool) | yes |
| `CHECKPOINTER_DB_URL` | `postgresql://…?options=-c%20search_path%3Dlanggraph` | checkpointer/store (psycopg3 pool) | yes |
| `OPENAI_API_KEY` | `sk-…` | `app/graph/llm.py` | yes |
| `MODEL_ROUTER` | small/fast snapshot | router + chitchat | no (id only) |
| `MODEL_AGENT` | mid snapshot | ReAct Q&A, briefing sections | no |
| `MODEL_CRITIC` | reasoning snapshot | prediction critic, briefing plan | no |
| `API_FOOTBALL_KEY` | provider key | `ApiFootballProvider` (`x-apisports-key`) | yes |
| `FOOTBALL_DATA_TOKEN` | provider token | `FootballDataProvider` (`X-Auth-Token`) | yes |
| `THE_ODDS_API_KEY` | provider key | `TheOddsApiProvider` (`apiKey` query) | yes |
| `JWT_SECRET` | random 32B+ | `app/security.py` (HS256 sign/verify) | yes |
| `JWT_ALG` | `HS256` | security | no |
| `ACCESS_TOKEN_TTL_MIN` | e.g. `60` | security | no |
| `GOOGLE_CLIENT_ID` | OAuth client id | `app/security.py` Authlib (Q5) | no (id only) |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret | Authlib Google flow | yes |
| `OAUTH_REDIRECT_URI` | `https://api…/api/auth/google/callback` | Authlib callback | no |
| `LANGSMITH_TRACING` | `true` | LangSmith auto-instrument | no |
| `LANGSMITH_API_KEY` | `ls-…` | LangSmith | yes |
| `LANGSMITH_PROJECT` | `pitch-iq` | LangSmith | no |
| `LANGGRAPH_AES_KEY` | optional 32B | `EncryptedSerializer` (at-rest checkpoint encryption) | yes |
| `RUN_SCHEDULER` | `false` web / `true` worker | `lifespan.py` (start APScheduler?) | no |
| `CORS_ORIGINS` | `https://app…,http://localhost:3000` | FastAPI CORS middleware | no |
| `LIVE_POLL_SECONDS` | `60` | poller cadence in live windows | no |
| `BRIEFING_LEAD_HOURS` | `2` | scheduler `'date'` offset | no |

### Frontend (`frontend/.env.example`)

| Var | Example | Consumer | Exposure |
|---|---|---|---|
| `BACKEND_URL` | `http://localhost:8000` | Route Handlers only (`api/chat`, `api/[...path]`) | **server-only — never `NEXT_PUBLIC_`** |
| `NEXT_PUBLIC_APP_URL` | `https://app.pitchiq…` | client (absolute URLs, share links) | public |

### Secrets handling rules

- **Never ship secrets to the browser.** `BACKEND_URL` is intentionally *not* `NEXT_PUBLIC_`; the proxy is the only thing that knows the FastAPI origin and the only thing that attaches the user's auth. The proxy injects the `Authorization: Bearer …` header server-side so the token is never read from a public env var.
- **`RUN_SCHEDULER` is the single switch** that distinguishes process 2 (web, `false`) from process 3 (worker, `true`). `lifespan.py` reads it and conditionally starts APScheduler. Misconfiguring it on >1 replica reintroduces Risk #4.
- **Two DB URLs on purpose.** `DATABASE_URL` (asyncpg) and `CHECKPOINTER_DB_URL` (psycopg3 with `search_path=langgraph`) point at the same instance but different schemas + drivers. They are distinct secrets so credentials/pool settings can diverge.
- **Optional at-rest encryption** via `LANGGRAPH_AES_KEY` enables `EncryptedSerializer` for checkpoint blobs. Its exact activation scope (platform vs. self-host) is Open Question #12/#10 — treat as optional until confirmed.
- **Local vs. prod:** `.env` (git-ignored) locally; platform secret manager in prod. `*.env.example` files are committed with placeholder values only.

---

## 5. Open questions touching architecture (do not assert as fact)

| # | Question | Impact on this doc |
|---|---|---|
| 5 | Does first-party `fastapi.sse.EventSourceResponse` exist in 0.138.2? Not adversarially verified. | We use `sse-starlette` 3.4.5 (verified). If first-party is confirmed it's a drop-in swap; SSE topology unchanged. |
| 2 | `astream_events(version="v3")` GA status. | Chat path ships `stream_mode="messages"` v2; v3 migration is gated, sequence diagram unaffected in shape. |
| ~~9~~ | ✅ **RESOLVED (Q4): Vercel + Railway + managed Postgres.** | Process 1 → Vercel; processes 2 & 3 → Railway services (web + single `RUN_SCHEDULER` worker); Postgres = Railway/Neon. 3-process model + single-scheduler rule unchanged. |
| ~~7~~ | ✅ **RESOLVED (Q2): shared-per-fixture.** | `briefings.user_id` NULL = shared; personalized bracket-impact overlay client-side. Briefing-path flow unchanged. |
| 10/12 | `EncryptedSerializer` scope when `LANGGRAPH_AES_KEY` set. | Keeps that env var optional for now. |

---

*This document is layer (a) — the runtime system. For how we build it (layer b), see `06-workflows/`. For graph internals see `02`; for the DB schema see `04`.*
