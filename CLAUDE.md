# Pitch IQ — Project Conventions

> Config-driven agentic tournament-companion web app. Launch config = FIFA World Cup 2026 (WC is a seed row + config, **not** the architecture).

**Source of truth:** [`docs/plan/research/canonical-spec.md`](docs/plan/research/canonical-spec.md). If anything here disagrees with the spec, the spec wins. Planning docs live in [`docs/plan/`](docs/plan/).

**Two layers — keep strictly separate:**
- **Runtime patterns** = LangGraph behavior *inside* the product.
- **Build workflows** = Claude Code dynamic-workflow orchestration used *to build* the product.

---

## Locked stack (pinned; versions trace to `docs/plan/research/09-decision-memo.md`)

**Backend** (Python ≥ 3.12): langgraph **1.2.7** · langchain **1.3.11** (`create_agent`) · langchain-openai **1.3.3** · langgraph-checkpoint-postgres **3.1.0** (`AsyncPostgresSaver`) · fastapi **0.138.2** · uvicorn **0.49.0** · sse-starlette **3.4.5** (`EventSourceResponse`) · APScheduler **3.11.3** (`AsyncIOScheduler` — **NOT 4.x alpha**) · SQLAlchemy **2.0.51** async + asyncpg **0.31.0** (app ORM) · psycopg[binary,pool] **3.3.4** (checkpointer pool only) · alembic **1.18.5** · pydantic 2.x · PyJWT + pwdlib[argon2] + Authlib (Google OAuth, ⚠️ pin at install) · langsmith[pytest] **0.9.3** · openevals **0.2.0**. Env/lockfile via **uv** (`uv.lock`).

**Frontend** (Node ≥ 22): next **16.2.9** (App Router, Turbopack) · react/react-dom **19.2.7** · ai **7.0.8** · @ai-sdk/react **4.0.9** (`useChat`) · @tanstack/react-query **5.101.2** · tailwindcss **4.3.2** (CSS-first `@theme`) · shadcn CLI **4.12.0**. Package manager + lockfile via **pnpm**.

OpenAI models resolved via `app/graph/llm.py` (`init_chat_model`): `MODEL_ROUTER` (small) / `MODEL_AGENT` (mid) / `MODEL_CRITIC` (reasoning). Exact snapshot ids = open question — verify against OpenAI's live model list before pinning.

---

## Key commands

| | Backend (`backend/`) | Frontend (`frontend/`) |
|---|---|---|
| install | `uv sync` | `pnpm install` |
| run | `uvicorn app.main:app --reload` | `pnpm dev` |

---

## Verification gates (a task is NOT done until these pass)

- **Backend:** `uv run ruff check . && uv run mypy app && uv run pytest -q`
- **Frontend:** `pnpm lint && pnpm typecheck && pnpm test && pnpm build`
- **Evals (nightly/PR-gated):** `uv run pytest -m langsmith` (use `LANGSMITH_TEST_CACHE` to avoid paying per commit)

---

## Core principles

- **Use the simplest approach that works — no speculative abstraction.** Do not over-engineer.
- **Config-driven engine — never hardcode the World Cup.** Tournament behavior comes from `tournaments.format_config` / `tournaments.scoring_config` (JSONB) + the provider abstraction (`app/providers/base.py` Protocols). Adding a 2nd tournament must require **zero schema DDL** — only new `tournaments` rows + provider id mapping.
- **Pin concrete versions; mark uncertain claims as open questions** rather than asserting them (see spec §9).

---

## Build-time orchestration (Claude Code)

- **Subagent roster:** [`.claude/agents/`](.claude/agents/) — `langgraph-builder`, `fastapi-builder`, `nextjs-builder`, `data-tool-researcher`, `test-writer`, `adversarial-reviewer`.
- **Tool allowlist for unattended workflow runs:** [`.claude/settings.json`](.claude/settings.json) (`permissions.allow`). Denies `git push`, destructive `rm -rf`, secret prints.
- **Model routing:** **Sonnet** for mechanical/boilerplate stages; **Opus 4.8** for graph design (wf-03/04), SSE (wf-06), adversarial reviewers, and eval design (wf-08).
- **Concurrency:** all workflow fan-outs ≤ 16. Run a one-unit slice first to gauge spend, then full fan-out.
