# Pitch IQ — Agentic Tournament Companion

A config-driven, agentic "tournament companion" web app. Launch config = **FIFA World Cup 2026**
(the World Cup is a seed row + config, **not** the architecture). Built faithfully to
[`docs/plan/research/canonical-spec.md`](docs/plan/research/canonical-spec.md).

It delivers four things, grounded in real live data:

1. **Agent-run chat companion** — intent-routed ReAct Q&A over live data. The chat streams the
   agent's working: which specialist it routed to, every tool call (with status), then the answer
   token by token.
2. **Predictions** — a generator→critic loop pressure-tests every call against the no-vig market
   line from The Odds API.
3. **Pre-match briefings** — orchestrator–worker map-reduce (stakes, key players, H2H, form),
   generated before kickoff.
4. **Bracket scoring + private leagues** — pick the knockouts, **lock with a human-in-the-loop
   confirmation**, score against real results, climb a private league table.

All **7 mandated LangGraph runtime patterns** are implemented: conditional routing · ReAct + tool
binding · parallelization · orchestrator–worker (Send) · generator–evaluator · memory
(checkpointer + store) · human-in-the-loop (`interrupt`).

---

## Live data (the important part)

WC2026 is sourced from **real APIs**, not mocks:

- **football-data.org** is the **primary** sports provider (`SPORTS_PRIMARY=football-data`). It carries
  the live 2026 World Cup — 104 matches, group stage finished, Round of 32 in progress. API-Football
  has the 2026 *season* registered but **zero fixtures published**, so it is the fallback only.
- **The Odds API** supplies real WC2026 odds for upcoming matches; the prediction critic de-vigs them
  (Pinnacle) into a fair market line.
- A deterministic `FakeProvider` stack is available for offline tests/CI (`USE_FAKE_PROVIDERS=true`).

The engine is provider-swappable behind `app/providers/base.py` Protocols, so re-pointing at another
competition is a `tournaments` row + provider mapping, with zero schema changes.

---

## Stack (pinned, installed in this repo)

**Backend** (Python ≥ 3.12): langgraph 1.2.7 · langchain 1.3.11 (`create_agent`) · langchain-openai
1.3.3 · langgraph-checkpoint-postgres 3.1.0 (`AsyncPostgresSaver`) · fastapi 0.138.2 · uvicorn 0.49.0
· sse-starlette 3.4.5 · APScheduler 3.11.3 · SQLAlchemy 2.0.51 + asyncpg · psycopg3 · alembic 1.18.5 ·
PyJWT + pwdlib[argon2] + Authlib · pydantic 2.x. Env via **uv**.

**Frontend** (Node ≥ 22): next 16.2.9 (App Router, Turbopack) · react 19.2 · @tanstack/react-query
5.101 · tailwindcss 4 (CSS-first `@theme`, OKLCH tokens) · lucide icons · react-markdown. The chat
reads a custom **NDJSON agent-run stream** through a `useCompanionChat` hook (no AI-SDK transport).
Package manager **pnpm**.

---

## Design

The interface is a **matchnight broadcast monitor**: cool ink neutrals in OKLCH, a single floodlight
amber accent, a reserved live-red, Archivo / Inter / JetBrains Mono, icons (no emoji). The agent run
is the signature element. The full brief and tokens live in [`PRODUCT.md`](PRODUCT.md) and
[`DESIGN.md`](DESIGN.md).

---

## Run it locally

Prerequisites: Docker, `uv`, Node ≥ 22 (`nvm use 22`), `pnpm`. Copy the example envs and add your own
keys (`backend/.env.example` → `backend/.env`; set `BACKEND_URL`/`NEXT_PUBLIC_API_BASE` for the
frontend). Secrets are git-ignored.

```bash
# 1) Postgres (app + langgraph schemas, port 5433)
docker compose up -d

# 2) Backend
cd backend
uv sync --extra dev
uv run alembic upgrade head        # create the app schema
uv run python scripts/seed.py      # import real WC2026 (48 teams, 104 fixtures) from football-data.org
uv run uvicorn app.main:app --reload --port 8000

# 3) Frontend (new terminal)
cd frontend
pnpm install
pnpm dev                           # http://localhost:3000
```

Open **http://localhost:3000**, register, and open the companion.

---

## Verification gates

```bash
# Backend
cd backend && uv run ruff check . && uv run mypy app && uv run pytest -q

# Frontend
cd frontend && pnpm lint && pnpm typecheck && pnpm build

# Live browser E2E (headless Chromium via Playwright; both servers running)
cd frontend && node e2e/run.mjs     # full HITL flow: register → bracket → submit/confirm → lock → predict
cd frontend && node e2e/shots.mjs   # screenshots of every page, desktop + mobile → /tmp/pitchiq-shots/
```

---

## Layout

```
backend/   FastAPI + LangGraph companion_graph, providers, services, scheduler, alembic
  app/graph/      state · router · llm · subgraphs/{qa_agent,prediction,briefing,bracket_ops} · tools · nodes · build
  app/providers/  base (Protocols + DTOs) · football_data (primary) · api_football · the_odds_api · caching · fake
  app/api/        health · auth · chat (NDJSON agent-run stream) · tournaments · brackets (HITL) · briefings · leagues
  app/db/ app/services/ app/scheduler/ app/memory/  scripts/seed.py  tests/
frontend/  Next.js App Router
  app/            (auth)/login·register · page (dashboard) · tournament/[slug] (companion) · bracket/[id] · league/[id] · api proxies
  components/     chat/{ChatPanel,RunTrace,…} · companion/RightRail · live/LiveMatchCard · bracket/* · ui/* (design system)
  lib/companionChat.ts   the agent-run streaming hook
docs/plan/ the canonical spec + planning docs this was built from
PRODUCT.md DESIGN.md   product context + design system
```

See `docs/plan/` for the authoritative design. Deployment topology (Vercel + Railway web/worker +
managed Postgres, single scheduler replica) is in `docs/plan/01-architecture.md`.
