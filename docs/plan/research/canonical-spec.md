# Pitch IQ — Canonical Design Spec (single source of truth)

**Status:** Locked for planning · **Date:** 2026-06-30 · derived from `09-decision-memo.md` + verified research streams.

> This file is the authoritative reference the planning docs (`../00`…`../10`, `../06-workflows/*`, root `CLAUDE.md`) are expanded from. If a planning doc disagrees with this spec, the spec wins. Every version here traces to `research/`. Two layers are kept strictly separate:
> - **Runtime patterns** = LangGraph behavior *inside the product*.
> - **Build workflows** = Claude Code dynamic-workflow orchestration used *to build the product*.

---

## 0. Product in one paragraph

**Pitch IQ** is an agentic "tournament companion" web app. A user picks a bracket and favorite teams; the app delivers (1) **pre-match briefings** (plain-language storyline + stakes + bracket implications), (2) **in/post-match Q&A** grounded in live data ("why 6 minutes added?", "was that offside?", "what does this result do to my bracket?"), (3) **predictions** that a critic pressure-tests against odds/form so they aren't naive, and (4) **bracket scoring + private friend leagues**. Launch config = **FIFA World Cup 2026** (live now, knockout stage). **Core principle:** it is a *config-driven tournament-companion engine* (any group/knockout event: Euro, Copa, UCL, March Madness, NFL playoffs), not WC-hardcoded. The WC is a seed row + config, not the architecture.

### MVP scope (in)
- Auth (email/JWT **+ Google OAuth** — Q5 resolved), favorite teams, one bracket per user per tournament, pick editing, **HITL-confirmed bracket submit/lock**.
- Streaming chat companion (SSE) with intent routing, ReAct Q&A over live data, rule explanations.
- Predictions with generator→critic loop.
- Scheduled pre-match briefings (per fixture, kickoff − 2h) + post-match recap.
- Bracket scoring + private leagues (invite code) + leaderboard.
- Live "what's happening" panel (events feed) for the user's relevant match.
- LangSmith tracing + an eval harness (routing accuracy, prediction calibration, groundedness).

### Non-goals (explicit, MVP)
- Native mobile apps; payments/subscriptions; public social feed; video highlights; multi-sport at launch (engine supports it, only football seeded); live odds *betting*/wagering; sub-second push (we poll); admin CMS; i18n beyond English; Sportradar-grade official feeds.

### Success criteria
- Time-to-first-token on chat < 1.5s p50; briefing generated and stored before kickoff for 100% of the user's relevant fixtures.
- Routing accuracy ≥ 0.9 macro-F1 on the eval set; prediction probabilities calibrated within a sane band of the no-vig market line (Brier ≤ market+0.02); groundedness pass-rate ≥ 0.95 (no fabricated numbers).
- Engine reused for a 2nd tournament config with **zero schema DDL** (only new `tournaments` rows + provider id mapping).

### Seasonal-window strategy
Ship the WC config fast (tournament is live; demand window is weeks). Keep everything behind config + a provider abstraction so the same engine is re-pointable at the next event with no rebuild — longevity without a rewrite. Cost-control the seasonal spike: poll providers only in live windows, cache aggressively, cheap models on hot paths.

---

## 1. Locked stack (pinned; sources in `research/09-decision-memo.md`)

### Backend (Python ≥ 3.12)
| Component | Version | Role |
|---|---|---|
| langgraph | **1.2.7** | graph runtime |
| langchain | **1.3.11** | `langchain.agents.create_agent` (ReAct) |
| langchain-core | **1.4.8** | messages/runnables |
| langchain-openai | **1.3.3** | OpenAI chat (pulls openai≥2.26,<3) |
| langgraph-checkpoint | **4.1.1** | base savers + `BaseStore` |
| langgraph-checkpoint-postgres | **3.1.0** | `AsyncPostgresSaver` (psycopg3) |
| langgraph-prebuilt | **1.1.0** | `ToolNode` |
| fastapi | **0.138.2** | API |
| starlette | **1.3.1** / uvicorn **0.49.0** | ASGI |
| sse-starlette | **3.4.5** | SSE transport (`EventSourceResponse`) — **chosen over** unverified first-party `fastapi.sse` |
| APScheduler | **3.11.3** (`AsyncIOScheduler`) | scheduler — **NOT 4.x (alpha)** |
| SQLAlchemy | **2.0.51** (async) + asyncpg **0.31.0** | app ORM — **not 2.1 beta** |
| psycopg[binary,pool] | **3.3.4** | checkpointer pool only |
| alembic | **1.18.5** | migrations (`init -t async`) |
| pydantic / pydantic-settings | **2.x** | schemas + env config |
| PyJWT + pwdlib[argon2] | latest (pin in lock) | email/password auth + session JWT (custom dep; fastapi-users avoided) |
| Authlib | latest (⚠️ pin + verify at install) | Google OAuth2 authorization-code flow (Q5 resolved) |
| langsmith[pytest] | **0.9.3** | tracing + CI evals |
| openevals | **0.2.0** | groundedness judges |
| agentevals | **0.0.9** ⚠️ confirm currency | trajectory eval |
| pytest, pytest-asyncio, httpx, respx | latest | testing |
| uv | latest | env + lockfile (`uv.lock`) |
| ruff + mypy | latest | lint/format/types |

### Frontend (Node ≥ 22)
| Component | Version | Role |
|---|---|---|
| next | **16.2.9** | App Router, Turbopack default |
| react / react-dom | **19.2.7** | UI |
| ai | **7.0.8** | Vercel AI SDK core |
| @ai-sdk/react | **4.0.9** ⚠️ verify peer vs ai@7 | `useChat` |
| @tanstack/react-query | **5.101.2** | server cache (fixtures/standings/bracket) |
| tailwindcss | **4.3.2** | styling (CSS-first `@theme`) |
| shadcn (CLI) | **4.12.0** | components (Tailwind v4 + React 19 native) |
| typescript, eslint, prettier, vitest, @playwright/test | latest | tooling/tests |
| pnpm | latest | package manager + lockfile |

**OpenAI models (swappable, config-driven via `app/graph/llm.py`).** Pin a concrete snapshot at build (OpenAI's current GPT-5.x line per research; **exact snapshot id is an open question — verify against OpenAI's live model list before pinning**). Convention: `MODEL_ROUTER` = small/fast (router, chitchat), `MODEL_AGENT` = mid (ReAct Q&A, briefing sections), `MODEL_CRITIC` = reasoning (prediction critic, briefing plan). All resolved by `init_chat_model(...)` so a non-OpenAI model is a config change.

---

## 2. System architecture

```
┌────────────────────────── Browser (Next.js 16 App Router) ──────────────────────────┐
│  /tournament/[slug] : 3-pane → ChatPanel · LivePanel · BracketBoard                   │
│  useChat(TextStreamChatTransport '/api/chat') · TanStack Query · EventSource live     │
└───────────────┬───────────────────────────────────────────────┬──────────────────────┘
       /api/chat (Route Handler proxy: hides BACKEND_URL,         │ /api/* proxy (auth header inject, CORS-free)
        injects auth, disables buffering)                         │
                ▼                                                 ▼
┌──────────────────────────────── FastAPI 0.138 (async) ───────────────────────────────┐
│  api/: chat(SSE) · auth · brackets · leagues · briefings · tournaments · health        │
│  lifespan singletons: compiled LangGraph · AsyncPostgresSaver · PostgresStore ·         │
│                       asyncpg engine · scheduler(single proc) · provider clients        │
│  ┌── LangGraph runtime (companion_graph) ──────────────────────────────────────────┐   │
│  │ ingest → router →{ qa_agent | prediction | briefing | bracket_ops | chitchat }    │   │
│  │            → persist_memory → END    (subgraphs = the 7 mandated patterns)         │   │
│  └────────────────────────────────────────────────────────────────────────────────┘   │
│  services: poller · scoring · briefing   tools → SportsDataProvider / OddsProvider      │
└───────┬───────────────────────────┬───────────────────────────────┬────────────────────┘
        ▼                           ▼                                 ▼
 Postgres (one instance)     Provider HTTP (REST, polling)      LangSmith (traces+evals)
 • app schema (asyncpg)      • API-Football (primary)
 • langgraph schema          • football-data.org (fallback)
   (psycopg3, search_path)   • The Odds API (odds→win prob)
```

**Deployment topology (MVP) — Q4 resolved = Vercel + Railway + managed Postgres:** 3 processes — (1) Next.js on **Vercel**, (2) FastAPI **web** service on **Railway** (uvicorn, scales horizontally; **scheduler disabled**, `RUN_SCHEDULER` unset), (3) a **single** FastAPI **worker** service on **Railway** = same image with `RUN_SCHEDULER=true` (exactly 1 replica, owns APScheduler + poller). One **managed Postgres** (Railway Postgres, or Neon) shared by both schemas + optional Redis later. Secrets via Vercel/Railway secret stores (`.env` local). LangSmith via env vars.

**Why single scheduler process:** APScheduler in-process under multiple uvicorn workers double-fires. One replica (or a Postgres advisory-lock leader election) guarantees one briefing per fixture.

### Env vars (canonical)
Backend: `DATABASE_URL` (asyncpg), `CHECKPOINTER_DB_URL` (psycopg3, `?options=-c%20search_path%3Dlanggraph`), `OPENAI_API_KEY`, `MODEL_ROUTER/MODEL_AGENT/MODEL_CRITIC`, `API_FOOTBALL_KEY`, `FOOTBALL_DATA_TOKEN`, `THE_ODDS_API_KEY`, `JWT_SECRET`, `JWT_ALG=HS256`, `ACCESS_TOKEN_TTL_MIN`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OAUTH_REDIRECT_URI`, `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGGRAPH_AES_KEY` (optional at-rest encryption), `RUN_SCHEDULER`, `CORS_ORIGINS`, `LIVE_POLL_SECONDS=60`, `BRIEFING_LEAD_HOURS=2`.
Frontend: `BACKEND_URL` (server-only), `NEXT_PUBLIC_APP_URL`.

---

## 3. LangGraph design (the 7 mandated runtime patterns)

**Top-level graph `companion_graph` (in `app/graph/build.py`).** A supervisor/router graph; each mandated pattern is a labeled **subgraph/module**. Checkpointer + store attach at `compile()`.

```
            ┌─────────┐
  START ──▶ │ ingest  │  load user_context from Store; resolve tournament/thread
            └────┬────┘
                 ▼
            ┌─────────┐   structured-output classify → Route enum
            │ router  │   ─────────────────────────────────────────────┐  (CONDITIONAL ROUTING)
            └────┬────┘                                                 │
   add_conditional_edges(router, pick_route, {...})                     │
        ┌────────────┬───────────────┬───────────────┬─────────────┐   │
        ▼            ▼               ▼               ▼             ▼   │
   ┌─────────┐  ┌──────────┐   ┌──────────┐   ┌────────────┐  ┌───────┐
   │qa_agent │  │prediction│   │ briefing │   │bracket_ops │  │chitchat│
   │(ReAct)  │  │(gen-eval)│   │(orch-wkr)│   │  (HITL)    │  │ (llm) │
   └────┬────┘  └────┬─────┘   └────┬─────┘   └─────┬──────┘  └───┬───┘
        └────────────┴──────────────┴───────────────┴────────────┘
                 ▼
          ┌──────────────┐  write durable facts to Store
          │persist_memory│  ──────────────────────────────▶ END
          └──────────────┘
```

### 3.1 State schema (`app/graph/state.py`) — strict Pydantic + TypedDict reducers
Graph state is a `TypedDict` (reducer support via `Annotated`); **all tool I/O and nested payloads are Pydantic `BaseModel`** with `model_config = ConfigDict(extra="forbid")`.

```python
class Route(str, Enum):
    MATCH_QA="match_qa"; RULES_QA="rules_qa"; BRACKET_QA="bracket_qa"
    PREDICTION="prediction"; BRIEFING="briefing"; BRACKET_OPS="bracket_ops"; CHITCHAT="chitchat"

class CompanionState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]   # add_messages reducer
    user_id: str
    tournament_id: str
    thread_id: str
    route: NotRequired[Route]
    intent: NotRequired[RouterDecision]                   # Pydantic: route + params + confidence
    user_context: NotRequired[UserContext]               # favorites, prefs, tone (from Store)
    gathered: Annotated[list[DataFragment], operator.add] # parallel fan-in channel
    prediction: NotRequired[Prediction]                  # Pydantic
    critique: NotRequired[Critique]                      # Pydantic (verdict, issues)
    prediction_round: NotRequired[int]
    briefing_plan: NotRequired[BriefingPlan]             # Pydantic (sections[])
    briefing_sections: Annotated[list[BriefingSection], operator.add]
    briefing: NotRequired[Briefing]
    pending_change: NotRequired[BracketChange]           # Pydantic
    approved: NotRequired[bool]
    final_response: NotRequired[str]
```
`context_schema=CompanionContext` injects per-run deps (provider clients, user tz) and gives nodes `runtime.store`.

### 3.2 Pattern → location → rationale (each is a labeled module)
| # | Pattern | Module | Where it lives / fires | One-line rationale |
|---|---|---|---|---|
| 1 | **Conditional routing** | `app/graph/router.py` | `router` node + `add_conditional_edges` | one cheap structured-output classifier picks the right specialist; testable as a closed-set classifier |
| 2 | **ReAct + tool binding** | `app/graph/subgraphs/qa_agent.py` | `langchain.agents.create_agent(model, tools=[...], checkpointer=True)` | live-data Q&A needs tool-use loops; prebuilt agent binds tools + streams messages |
| 3 | **Parallelization** | `app/graph/subgraphs/briefing.py` (`gather_*` fan-out) & `prediction.py` (`gen`∥`fetch_market`) | static fan-out edges → `operator.add` channel `gathered`; `defer=True` fan-in | independent data pulls run concurrently → lower latency |
| 4 | **Orchestrator–worker** | `app/graph/subgraphs/briefing.py` | `plan_briefing` → `Send("write_section", spec)` per section → `assemble` (defer) | section count is data-dependent; **Send API** map-reduce |
| 5 | **Generator–evaluator** | `app/graph/subgraphs/prediction.py` | `gen_prediction` → `critic` → conditional loop back (≤2 rounds) → `finalize` | critic pressure-tests vs no-vig odds + form so predictions aren't naive |
| 6 | **Memory (checkpointer + store)** | `app/graph/build.py`, `ingest`, `persist_memory` | `compile(checkpointer=AsyncPostgresSaver, store=PostgresStore)`; thread_id per conversation | short-term thread state + HITL durability (checkpointer) + cross-thread user facts (store) |
| 7 | **Human-in-the-loop** | `app/graph/subgraphs/bracket_ops.py` | `interrupt(change_summary)` in `confirm` node; resume `Command(resume=bool)` | locking/submitting a bracket is consequential → explicit approval before the write |

### 3.3 Subgraph detail
- **router**: LLM with `.with_structured_output(RouterDecision)` (OpenAI strict json_schema, enum-closed). `pick_route(state)->Route`. Low-confidence → `CHITCHAT` (asks a clarifying question).
- **qa_agent** (ReAct): tools bound = `get_fixture, get_live_match_state, get_lineups, get_standings, get_head_to_head, get_team_form, get_bracket_status, explain_rule`. System prompt forbids stating unverified facts; must call a tool for any live claim. Streams tokens (this is the main chat path).
- **prediction** (gen-eval, parallel inside):
  ```
  START → [gen_prediction ∥ fetch_market] → critic → (revise? loop≤2 : finalize) → END
  fetch_market → OddsProvider de-vig → WinProbabilities; gen_prediction → Prediction(probs, scoreline, drivers)
  critic → Critique(verdict in {pass,revise}, issues[], market_delta)  ; loop edge if revise & round<2
  ```
  Critic rubric: probabilities valid+sum→1; within sane band of market; rationale cites form not vibes; flags favorite-bias.
- **briefing** (orch-worker + parallel):
  ```
  START → fan-out gather_{fixture,lineups,standings,odds,h2h,form} (∥, operator.add→gathered)
        → plan_briefing (orchestrator: choose sections by stakes + user bracket)
        → Send("write_section", spec) per section (∥ workers)
        → assemble (defer=True fan-in) → END
  Sections: stakes, key_players, bracket_impact, head_to_head, form_and_prediction, how_it_works(rules)
  ```
  Invoked two ways: by chat route `BRIEFING`, and **headless by the scheduler** (`briefing_service` calls the subgraph directly with a system thread_id).
- **bracket_ops** (HITL):
  ```
  START → validate_change → confirm[interrupt(summary)] → (approved? apply_change : cancel) → END
  ```
  `apply_change` is the only consequential write (lock/submit). Node is **idempotent** (interrupt re-runs node top on resume; side effects after interrupt; deterministic interrupt order; never bare-except around interrupt()). `durability="sync"` for this run.

### 3.4 Streaming + interrupts surfacing
- **MVP token stream:** `graph.astream(input, config, stream_mode="messages")` (**version="v2"**, stable) → `(chunk, meta)`; filter `meta["langgraph_node"]` to the user-facing node(s). The newer typed-projection `astream_events(version="v3")` is recommended-but-**beta**; migrate behind GA (Risk #2).
- **Interrupts:** bracket_ops runs via the brackets API (not the chat stream). The submit endpoint runs the graph; if it returns an interrupt, respond `409`-style payload `{interrupt:{id,summary}}`; the confirm endpoint resumes with `Command(resume=True/False)`.

---

## 4. Data + provider abstraction

### 4.1 Tool-interface abstraction (provider-swappable)
`app/providers/base.py` defines `Protocol`s + Pydantic models; tools in `app/graph/tools/sports.py` depend **only** on the protocol, never a concrete client.
```python
class SportsDataProvider(Protocol):
    async def list_fixtures(self, t: TournamentRef, *, date=None, live=False) -> list[Fixture]: ...
    async def get_fixture(self, ref: ProviderRef) -> Fixture: ...
    async def get_live_state(self, ref: ProviderRef) -> LiveMatchState: ...
    async def get_lineups(self, ref: ProviderRef) -> Lineups: ...
    async def get_standings(self, t: TournamentRef) -> Standings: ...
    async def get_head_to_head(self, a: TeamRef, b: TeamRef) -> HeadToHead: ...
    async def get_team_form(self, team: TeamRef, n: int = 5) -> TeamForm: ...
class OddsProvider(Protocol):
    async def get_match_odds(self, a: TeamRef, b: TeamRef, kickoff) -> MatchOdds: ...      # raw decimal
    async def get_win_probabilities(self, a, b, kickoff) -> WinProbabilities: ...          # de-vigged
```
Implementations: `ApiFootballProvider` (primary), `FootballDataProvider` (fallback), `TheOddsApiProvider`; `CachingProvider` decorator (TTL cache + token-bucket rate limit + live/idle cadence + provider-failover to fallback); `FakeProvider` (deterministic fixtures for tests/CI). Selected via `settings` (factory in `app/providers/__init__.py`).

### 4.2 Chosen providers (verified, see research/03 & 09)
- **Primary** API-Football v3 — base `https://v3.football.api-sports.io`, header `x-apisports-key`. **WC2026 = `league=1, season=2026`.** Full live state/events (`/fixtures?live=all`, `/fixtures/events`, ~15s refresh), lineups, 12-group standings, H2H. **Free = 100 req/day + 10 req/min** → prototyping only; **live needs Pro $19/mo (7,500/day)**. Coverage flags true but "may vary per match" — handle missing lineups/events.
- **Fallback** football-data.org v4 — base `https://api.football-data.org/v4`, header `X-Auth-Token`, competition code `WC`. Free fixtures/results/standings (scores **delayed**; live = €12/mo add-on). Attribution required. Used for reconciliation + cold backup.
- **Odds** The Odds API v4 — base `https://api.the-odds-api.com`, `apiKey` query param, sport `soccer_fifa_world_cup`, market `h2h` (3-way), `oddsFormat=decimal`. De-vig: `p_i=(1/d_i)/Σ(1/d_j)`, anchor **Pinnacle**. Free 500/mo → $30/mo (20k). Show "18+ Gamble Responsibly" if odds surfaced; never resell raw odds.
- **Sportradar: deferred** (B2B ~$10k+/mo; ToS §2.1 prediction-market clause may bar our use).

### 4.3 Rate-limit / polling strategy
Token-bucket per provider in `CachingProvider`. Cadences: fixtures/standings TTL 6–24h (refresh near kickoff); **live** poll `LIVE_POLL_SECONDS=60` **only while a relevant fixture is in `live` window**; odds refresh ≤ 6h pre-match. The `poller` service (scheduler-owned) writes live state to the `fixtures` cache + emits SSE for the live panel. Stay within free/Pro daily caps; 429 → exponential backoff → failover to football-data.org.

### 4.4 Pydantic data models (`app/providers/base.py`)
`ProviderRef(provider:str, id:str)`, `TeamRef`, `TournamentRef`, `Team`, `Fixture(status, kickoff, home/away, score, score_et, pens, venue, round_key, group)`, `MatchEvent(minute, extra, type, detail, team, player, assist)`, `LiveMatchState(status, minute, extra, score, events[])`, `Lineups(home_xi, away_xi, formations, bench)`, `Standings(groups[GroupTable])`, `HeadToHead`, `TeamForm(last_n[], wdl)`, `MatchOdds(bookmaker, home, draw, away)`, `WinProbabilities(home, draw, away, source, devig=True)`, `DataFragment(kind, payload)` (fan-in wrapper).

---

## 5. Persistence

- **Checkpointer:** `AsyncPostgresSaver` (langgraph-checkpoint-postgres 3.1.0) on Postgres, **`langgraph` schema** via psycopg3 pool with `options='-c search_path=langgraph'`, `autocommit=True, row_factory=dict_row, prepare_threshold=0`. `await checkpointer.setup()` once in lifespan. `durability="sync"` for HITL/scoring runs.
- **Store:** `AsyncPostgresStore` (prod) / `InMemoryStore` (dev) — long-term cross-thread user facts namespaced `("user", user_id)`.
- **App DB:** SQLAlchemy 2.0 async + asyncpg, **same instance** as checkpointer, **`app` schema**. Alembic async migrations. No cross-schema FK to checkpointer tables (join logically on `conversations.thread_id`).

### App schema (config-driven; PK `id uuid` unless noted) — authoritative
- **users**(email citext uniq, display_name, **password_hash nullable** (null for OAuth-only accounts), **auth_provider** [`password`|`google`], **auth_subject** (provider user id, nullable; uniq(auth_provider,auth_subject)), timezone, locale, created_at, updated_at)
- **tournaments**(slug uniq, name, sport='football', start_date, end_date, status, **format_config jsonb**, **scoring_config jsonb**) — *the config that de-hardcodes the engine*
- **teams**(name, short_name, country_code, crest_url, external_ref jsonb, …) — global, reused
- **tournament_teams**(tournament_id fk, team_id fk, group_label, seed, uniq(tournament_id,team_id))
- **favorite_teams**(user_id fk, team_id fk, uniq(user_id,team_id))
- **fixtures**(tournament_id fk, external_ref jsonb, stage, round_key, group_label, home_team_id?, away_team_id?, home_placeholder, away_placeholder, kickoff_at, venue, status, home_score, away_score, *_et, *_pens, winner_team_id, raw jsonb, fetched_at, updated_at) — match cache
- **brackets**(user_id fk, tournament_id fk, name, status[draft|submitted|locked|scored], submitted_at, total_score int, created_at, updated_at, uniq(user_id,tournament_id,name))
- **bracket_picks**(bracket_id fk, fixture_id fk?, round_key, pick_type, predicted_* (winner/home/away team + scores + generic team), points_awarded int?, is_correct bool?, scored_at)
- **leagues**(tournament_id fk, name, owner_user_id fk, invite_code uniq, visibility='private', scoring_config jsonb?, max_members)
- **league_memberships**(league_id fk, user_id fk, role, bracket_id fk?, joined_at, uniq(league_id,user_id))
- **briefings**(fixture_id fk, tournament_id fk, user_id fk **nullable** (null=shared/generic, set=personalized), type[pre_match|post_match|daily], status[pending|generating|ready|failed], content text, content_format='markdown', model, thread_id text?, generated_at, error)
- **conversations**(user_id fk, thread_id text uniq, tournament_id fk?, title, last_message_at, metadata jsonb) — **logical join to checkpointer `checkpoints.thread_id`**

**Scoring:** rules in `tournaments.scoring_config` (override per `leagues.scoring_config`); `scoring_service` settles each `bracket_picks` row vs `fixtures` outcome → `points_awarded/is_correct`; `brackets.total_score` denormalized for leaderboard reads.

---

## 6. Backend project structure + endpoints

```
backend/
  pyproject.toml  uv.lock  alembic.ini  .env.example  Dockerfile
  alembic/ (env.py async, versions/)
  app/
    main.py            # FastAPI(), include routers, CORS, lifespan
    config.py          # pydantic-settings Settings
    lifespan.py        # build graph + savers + store + pools + scheduler(if RUN_SCHEDULER)
    deps.py            # get_settings, get_db, get_state, get_current_user
    security.py        # PyJWT HS256 + pwdlib[argon2] + Authlib Google OAuth client
    api/  health.py auth.py chat.py brackets.py leagues.py briefings.py tournaments.py
    schemas/  auth.py chat.py bracket.py league.py briefing.py tournament.py common.py
    db/  base.py models.py session.py repositories/{users,brackets,leagues,fixtures,briefings,conversations}.py
    graph/  state.py build.py router.py llm.py
            nodes/{ingest,chitchat,persist_memory}.py
            subgraphs/{qa_agent,prediction,briefing,bracket_ops}.py
            tools/{__init__,sports,bracket,rules}.py
    providers/  base.py api_football.py football_data.py the_odds_api.py caching.py fake.py __init__.py
    services/  briefing_service.py scoring_service.py poller.py
    scheduler/  scheduler.py jobs.py
    memory/  store.py
    eval/  datasets/{routing.jsonl,predictions.jsonl,groundedness.jsonl} evaluators.py run_evals.py
  tests/  conftest.py unit/ integration/ eval/
```

### Endpoints (signatures; all async; `/api` prefix; JWT except auth/health)
- `GET  /healthz` → `{status}`
- `POST /api/auth/register` (RegisterIn)→`TokenOut`; `POST /api/auth/login`(OAuth2 form)→`TokenOut`; `GET /api/auth/google/login`→302 redirect to Google; `GET /api/auth/google/callback`(code,state)→`TokenOut` (Authlib; upsert user by `auth_subject`); `GET /api/me`→`UserOut`
- `PUT  /api/me/favorite-teams`(FavTeamsIn)→`UserOut`
- `POST /api/chat`(ChatIn{thread_id?,message,tournament_id})→**`EventSourceResponse`** (events: `token`, `tool`, `done`); proxied by Next `/api/chat`
- `GET  /api/tournaments/{slug}`→`TournamentOut`; `/{slug}/fixtures`→`[FixtureOut]`; `/{slug}/standings`→`StandingsOut`
- `GET  /api/fixtures/{id}`→`FixtureOut`; `GET /api/fixtures/{id}/live`→**SSE** event feed (live panel)
- Brackets: `POST /api/brackets`→`BracketOut`; `GET /api/brackets?tournament_id=`; `GET /api/brackets/{id}`; `PATCH /api/brackets/{id}/picks`(PicksIn)→`BracketOut`; `POST /api/brackets/{id}/submit`→`{interrupt}|BracketOut`; `POST /api/brackets/{id}/submit/confirm`(ConfirmIn{approved})→`BracketOut`; `GET /api/brackets/{id}/score`→`ScoreOut`
- Briefings: `GET /api/fixtures/{id}/briefing?type=pre_match`→`BriefingOut`; `POST /api/briefings/{fixture_id}/generate`(admin/manual)→`{job_id}`
- Leagues: `POST /api/leagues`→`LeagueOut`; `POST /api/leagues/join`(JoinIn{invite_code,bracket_id})→`LeagueOut`; `GET /api/leagues/{id}/leaderboard`→`LeaderboardOut`

### Scheduler jobs (`app/scheduler/jobs.py`)
- `schedule_briefings(tournament_id)` — scan upcoming fixtures, for each add `'date'` job `generate_briefing(fixture_id)` at `kickoff − BRIEFING_LEAD_HOURS`, id `briefing:{fixture_id}`, `replace_existing=True`.
- `generate_briefing(fixture_id)` — call `briefing_service` (runs briefing subgraph headless), upsert `briefings`.
- `poll_live()` — interval job (`LIVE_POLL_SECONDS`) active only during live windows; updates `fixtures` cache + pushes SSE; triggers `score_settled_fixtures()` on FT.
- `nightly_sync()` — cron: refresh fixtures/standings, (re)schedule briefings, reconcile vs fallback.

### Error handling / testing
Typed exceptions (`ProviderError`, `RateLimitError`, `AuthError`, `NotFound`) → exception handlers → RFC-9457 problem+json. Tests: pytest + pytest-asyncio + httpx ASGITransport; `respx` mocks provider HTTP; `FakeProvider` + `InMemorySaver` for graph tests; SSE smoke test asserts token frames; graph unit tests assert routing + interrupt/resume + critic-loop termination.

---

## 7. Frontend project structure + wiring

```
frontend/
  package.json  pnpm-lock.yaml  next.config.ts  tsconfig.json  postcss.config.mjs  components.json  .env.example
  app/
    layout.tsx  globals.css(@import shadcn/tailwind)  page.tsx(dashboard)
    (auth)/login/page.tsx  (auth)/register/page.tsx
    tournament/[slug]/page.tsx     # 3-pane companion (Server Component prefetch → HydrationBoundary)
    bracket/[id]/page.tsx          # bracket editor
    league/[id]/page.tsx           # leaderboard
    api/chat/route.ts              # SSE proxy → FastAPI (no-transform, X-Accel-Buffering:no, auth inject)
    api/[...path]/route.ts         # generic JSON proxy → FastAPI
  components/
    chat/{ChatPanel,MessageList,MessageBubble,Composer,ToolBadge}.tsx
    bracket/{BracketBoard,MatchNode,PickEditor,SubmitConfirmDialog}.tsx   # SubmitConfirmDialog = HITL UI
    live/{LivePanel,EventFeed,MatchHeader}.tsx
    briefing/{BriefingCard,BriefingList}.tsx
    league/{Leaderboard,InvitePanel}.tsx
    ui/  # shadcn primitives (Card, Tabs, Badge, ScrollArea, Avatar, Skeleton, Dialog, Sonner, …)
  lib/  api.ts  types.ts  queries.ts(TanStack hooks)  format.ts
  providers/  QueryProvider.tsx
  hooks/  useLiveFeed.ts
```

**Streaming wiring (corrected per verdict):** `useChat({ transport: new TextStreamChatTransport({ api: '/api/chat' }) })` — **text protocol** (the full UI-message/data protocol has open FastAPI issues; text is the dependable MVP path; upgrade later). `/api/chat` Route Handler proxies to FastAPI (hides `BACKEND_URL`, injects auth, disables buffering). **Non-streaming data** (bracket/fixtures/standings) via TanStack Query (server `prefetchQuery` → `HydrationBoundary` → `refetchInterval` in live windows). **Live panel** subscribes to `/api/fixtures/{id}/live` (EventSource via proxy or `useLiveFeed` fetch-stream), appends events, and `queryClient.setQueryData` updates cached standings. **HITL UI:** `SubmitConfirmDialog` shows the interrupt summary; confirm → `POST submit/confirm`. Three decoupled streams (chat / live / query cache), one coherent cache. Design system = **shadcn/ui on Tailwind v4**, World-Cup theming via tokens; bracket board = Tailwind grid of `Card` nodes + connector lines (no shadcn bracket primitive).

---

## 8. Build workflows (Claude Code orchestration to BUILD the product)

8 phases. **Mode rule:** dynamic workflow when parallelizable across many independent units / benefits from adversarial cross-check; turn-by-turn when small, tightly-coupled, sequential, or needs mid-stream human sign-off. **Sign-off = boundary between two workflows, never an interrupt inside one.**

| WF | Goal | Depends on | Mode | Fan-out | Verifier | Save-as-cmd |
|---|---|---|---|---|---|---|
| wf-01 foundations | monorepo, tooling, CI skeleton, `.env`, root CLAUDE.md, agent roster, allowlist | — | **turn-by-turn** (small, sequential, sign-off) | n/a | smoke: installs + lints pass | no |
| wf-02 data-tools | provider abstraction + impls + Pydantic models + tests (mock HTTP) | wf-01 | **workflow** | ~7 (base+models, api_football, football_data, the_odds_api, caching, fake, tests) | adversarial reviewer vs base.py protocol + respx tests | maybe (`/verify-providers`) |
| wf-03 core-graph | state schema, router, ReAct qa_agent, tool binding, llm factory | wf-02 | **turn-by-turn** (spine, tightly coupled) | 2-3 subagents | reviewer: routing unit tests + graph compiles | no |
| wf-04 advanced-graph | prediction (gen-eval), briefing (orch-worker+parallel) subgraphs | wf-03 | **workflow** | 3 (prediction, briefing, wiring) | adversarial reviewer: critic loop terminates, Send fan-in | no |
| wf-05 memory-hitl | AsyncPostgresSaver + Store + bracket_ops interrupts | wf-03 | **turn-by-turn** (coupled, HITL UX sign-off) | 2 | reviewer: interrupt/resume durability test | no |
| wf-06 api-streaming | FastAPI endpoints + SSE + scheduler/briefing pipeline | wf-04, wf-05 | **workflow** (after a turn-by-turn SSE spike) | ~6 (auth, chat-SSE, brackets, leagues+briefings, tournaments, scheduler) | adversarial reviewer vs §6 signatures + httpx/SSE tests | yes (`/review-endpoints`) |
| wf-07 frontend | Next chat + live panel + bracket board wired to backend | wf-06 | **workflow** | ~6 (proxy+providers, chat, bracket, live, league, dashboard/auth) | reviewer: typecheck + Playwright smoke + visual | maybe |
| wf-08 integration-verification | e2e flow, eval harness, observability, deploy | wf-06, wf-07 | **turn-by-turn** (cross-cutting, final sign-off) | small + eval-dataset sub-workflow | adversarial e2e reviewer + eval thresholds | yes (`/eval`) |

**Concurrency:** all fan-outs ≤ 16 (cap respected). **Model routing:** mechanical/boilerplate stages → cheaper model (Sonnet); graph design (wf-03/04), SSE (wf-06), adversarial reviewers, eval design (wf-08) → Opus 4.8. **Cost control:** run each large workflow on a one-unit slice first (one provider / one endpoint / one component) to gauge spend, then full fan-out.

### Subagent roster (`.claude/agents/`)
| Agent | Role | Tools (allowlist) | Model |
|---|---|---|---|
| `langgraph-builder` | graph nodes/subgraphs/tools | Read,Edit,Write,Grep,Glob,Bash(uv,pytest),context7,WebFetch | Opus (design) / Sonnet (mechanical) |
| `fastapi-builder` | endpoints, SSE, DB, scheduler | Read,Edit,Write,Grep,Glob,Bash(uv,pytest,alembic),context7 | Sonnet (Opus for SSE) |
| `nextjs-builder` | components, streaming, proxy | Read,Edit,Write,Grep,Glob,Bash(pnpm),shadcn MCP,context7 | Sonnet |
| `data-tool-researcher` | provider impls, verify live API shapes | Read,Edit,Write,Bash(uv),WebSearch,WebFetch,context7 | Sonnet (Opus if API ambiguous) |
| `test-writer` | pytest/vitest/Playwright | Read,Edit,Write,Grep,Glob,Bash(uv,pytest,pnpm,playwright) | Sonnet |
| `adversarial-reviewer` | break worker output vs spec/tests | Read,Grep,Glob,Bash(uv,pytest,pnpm) | Opus |

### Tool allowlist for unattended runs (`.claude/settings.json` permissions.allow)
`Read, Edit, Write, Grep, Glob`, `Bash(uv:*)`, `Bash(uv run:*)`, `Bash(pytest:*)`, `Bash(ruff:*)`, `Bash(mypy:*)`, `Bash(alembic:*)`, `Bash(pnpm:*)`, `Bash(npx shadcn:*)`, `Bash(git:*)` (no push), `WebFetch`, `WebSearch`, `mcp__context7__*`, `mcp__shadcn__*`. Deny: `Bash(git push:*)`, destructive `rm -rf`, secret prints.

---

## 9. Cross-cutting

### Sign-off boundaries (between workflows)
0 (now) approve provider+graph+stack → 1 after wf-01 conventions → 2 after wf-02 provider abstraction + WC data flows → 3 after wf-03 graph spine/routing → 4 after wf-05 HITL UX → 5 after wf-06 public API shape → 6 after wf-07 UX → 7 wf-08 ship.

### Testing/verification (test pyramid + commands)
- Unit (most): providers (respx), tools, scoring, router classify, schema validation.
- Integration: graph runs (FakeProvider+InMemorySaver), endpoints (httpx ASGITransport), SSE smoke, interrupt/resume, alembic upgrade head.
- E2E (few): Playwright — login→pick bracket→submit(confirm dialog)→chat streams→briefing shows.
- Eval (LangSmith pytest): routing macro-F1, prediction Brier/log-loss/ECE vs market, groundedness/hallucination rate, refusal rate. `LANGSMITH_TEST_CACHE` to avoid paying per commit.
- **Gate commands:** backend `uv run ruff check . && uv run mypy app && uv run pytest -q`; frontend `pnpm lint && pnpm typecheck && pnpm test && pnpm build`; evals `uv run pytest -m langsmith` (nightly/PR-gated).

### Top risks (mitigations)
1 API-Football free too thin → budget Pro $19/mo, poll only live, cache, fallback. 2 v3 streaming beta → ship stream_mode="messages" v2. 3 AI SDK data-protocol broken for FastAPI (#7496) → text protocol + proxy. 4 APScheduler multi-worker double-fire → single scheduler process. 5 interrupt() re-runs node → idempotent, side-effects-after-interrupt. 6 checkpointer/app schema collision → separate schemas + psycopg3 pool settings. 7 odds/legal (prediction-market clause, gambling) → no Sportradar, derive from Odds API, 18+ messaging. 8 bleeding-edge version drift → exact lockfiles + CI smoke + verify peers at install.

### Open questions (need user/build-time decision)
1 Exact OpenAI snapshot ids for router/agent/critic (verify vs live model list). 2 `@ai-sdk/react`↔`ai@7.0.8` peer pairing (confirm at install). 3 `agentevals 0.0.9` currency. 4 langgraph `durability` default + whether wired to ainvoke (#5741). 5 first-party `fastapi.sse` exists in 0.138.2? (else sse-starlette stands). 6 football-data.org redistribution/caching ToS for commercial use. 7 ✅ **RESOLVED (Q2):** briefings **shared-per-fixture** (`briefings.user_id` NULL = shared; personalized bracket-impact overlay client-side). 8 **Product (OPEN, Q3):** leagues season-long (multi-tournament) vs single-tournament — default single-tournament. 9 ✅ **RESOLVED (Q4):** hosting = **Vercel (frontend) + Railway (web + single scheduler worker) + managed Postgres**. 10 ✅ **RESOLVED (Q5):** auth = email/password JWT **+ Google OAuth** (Authlib) in MVP. 11 ✅ **RESOLVED (Q7):** budget baseline ≈ **$50–90/mo** (API-Football Pro $19 + The Odds API $30 + LangSmith free; football-data.org free fallback). 12 **OPEN (Q6):** `EncryptedSerializer` scope (self-host vs platform) — default enable if checkpoints hold PII. **Still OPEN:** OpenAI snapshot ids (Q1) + leagues scope (Q3) + encryption (Q6).
