# Research: PERSISTENCE

> Cited synthesis from the Pitch IQ research workflow (run 2026-06-30). Versions/URLs are primary-source-verified; see open questions for unresolved items.

**Executive summary:** For an async FastAPI app in 2026 the recommended Postgres access layer is SQLAlchemy 2.0.x async with the asyncpg driver. SQLAlchemy 2.0.51 (Jun 15 2026) is the current stable; 2.1 is still beta (2.1.0b3, Jun 27 2026) and SQLModel still pins SQLAlchemy <2.1, so stay on 2.0.x for now. asyncpg 0.31.0 is the fastest async PG driver and is the dialect SQLAlchemy's own async docs use (postgresql+asyncpg://). SQLModel 0.0.39 is viable for model/schema ergonomics but still does not wrap AsyncEngine/AsyncSession (you drop to SQLAlchemy async constructs anyway), so for a checkpointer-heavy app I recommend plain SQLAlchemy 2.0 async ORM and reserve SQLModel as an optional ergonomic layer. Alembic 1.18.5 is current and ships an official async migration template (alembic init -t async). Put the LangGraph Postgres checkpointer (langgraph-checkpoint-postgres 3.1.0, which uses psycopg3 3.3.4) in the SAME Postgres instance but an ISOLATED schema; note the Python AsyncPostgresSaver has no schema= argument (only the JS port does), so isolate via the connection's search_path. A config-driven tournament schema (JSONB format_config + scoring_config keyed off a tournaments row) keeps everything extensible to any group/knockout competition rather than hard-coding World Cup 2026. Bracket scoring is stored as rules in JSONB (tournament-level, optionally league-overridden), per-pick points_awarded/is_correct, and a denormalized brackets.total_score for fast leaderboards.

---

## Persistence stream: app database + ORM (FastAPI, async, 2026)

This covers the **application** database and ORM. The LangGraph checkpointer is owned by another stream; here it is only addressed where it touches the app DB (co-location).

### 1. Postgres access layer for async FastAPI

**Recommendation: SQLAlchemy 2.0.x async ORM + asyncpg.** SQLAlchemy 2.0 has mature first-class asyncio support (`create_async_engine`, `AsyncSession`), and its own [asyncio docs](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) use the `postgresql+asyncpg://` URL throughout. The current stable is **SQLAlchemy 2.0.51** (released Jun 15 2026 per [PyPI](https://pypi.org/project/SQLAlchemy/)). **Do not** jump to 2.1 yet: it is still beta (**2.1.0b3**, Jun 27 2026, same PyPI page).

The async driver is **asyncpg 0.31.0** (released Nov 24 2025, supporting Python 3.9-3.14 and PostgreSQL 9.5-18, per [PyPI](https://pypi.org/project/asyncpg/)). Note: a web-search summary asserted "asyncpg 3.2.1" — that is wrong; PyPI confirms the real line is 0.31.0. asyncpg is the standard high-performance choice for SQLAlchemy async with Postgres.

**SQLModel** ([0.0.39](https://pypi.org/pypi/sqlmodel/json), Jun 25 2026) is the FastAPI author's Pydantic+SQLAlchemy unification and is attractive because one class serves as DB model, validation model, and API schema, reducing duplication ([TestDriven.io](https://testdriven.io/blog/fastapi-sqlmodel/)). Two caveats make it a *secondary* choice for this app: (a) it still pins `SQLAlchemy<2.1.0,>=2.0.14` and `pydantic>=2.11.0`, so it constrains your SQLAlchemy upgrade path; and (b) it still has no `AsyncEngine`/`AsyncSession` wrappers — you import and use SQLAlchemy's async constructs directly anyway. For an app with non-trivial relations, scoring queries, and Alembic migrations, I recommend **plain SQLAlchemy 2.0 async** as the core, with SQLModel optional only if the team values its model ergonomics.

**Migrations: Alembic 1.18.5** (Jun 25 2026, [PyPI](https://pypi.org/project/alembic/)). Use the official async scaffold: `alembic init -t async`. That template's `env.py` runs `run_migrations_online()` through an `AsyncEngine`, executing the sync migration body via `connection.run_sync(...)` (greenlet bridge). Point `sqlalchemy.url` at the asyncpg URL and set `target_metadata` to your SQLAlchemy `Base.metadata` for autogenerate.

### 2. Should the LangGraph checkpointer share the app's Postgres?

**Yes — same instance, isolated schema.** The checkpointer (`langgraph-checkpoint-postgres` [3.1.0](https://pypi.org/project/langgraph-checkpoint-postgres/), May 12 2026) creates four tables via `setup()`: `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations` (cross-checked: [LangChain persistence docs](https://docs.langchain.com/oss/python/langgraph/persistence) and a [checkpointer internals write-up](https://blog.lordpatil.com/posts/langgraph-postgres-checkpointer/)).

| Option | Pros | Cons |
|---|---|---|
| Same instance, **separate schema** (recommended) | One DB to run/back up; transactional locality; clean namespace separation; `setup()` manages its own DDL | Checkpoint write volume shares IOPS with app OLTP |
| Same instance, same (public) schema | Simplest | Name collisions, mixed migration ownership, messier `\dt` |
| Separate instance | Full isolation of write load | More ops, two backups, no cross-DB transactions |

**Practical isolation detail (important):** the Python `AsyncPostgresSaver` constructor accepts only `conn`, `pipe`, `serde` — there is **no `schema=` parameter** (verified against the [AsyncPostgresSaver API reference](https://reference.langchain.com/python/langgraph.checkpoint.postgres/aio/AsyncPostgresSaver); only the JS/TS port exposes a `schema` option). So to keep checkpointer tables out of `public`, set the connection's `search_path` (e.g. psycopg connect `options='-c search_path=langgraph'`). Also note a **driver split**: the checkpointer uses **psycopg3** ([3.3.4](https://pypi.org/project/psycopg/), May 1 2026) while the app ORM uses **asyncpg** — run them as two separate pools. For the checkpointer pool, the documented production settings are `autocommit=True`, `row_factory=dict_row`, and `prepare_threshold=0` behind a pooler like PgBouncer. The open [docs issue #465](https://github.com/langchain-ai/docs/issues/465) shows official schema-customization docs are still pending, so verify behavior against the exact version you deploy.

Net: one Postgres instance, app tables in `app` (or `public`), checkpointer tables in a `langgraph` schema. Split instances later only if checkpoint writes contend with app traffic.

### 3. Proposed schema (config-driven, any group/knockout tournament)

Design principle: **never hard-code World Cup 2026.** A single `tournaments` row carries the structure and scoring as JSONB, and everything else keys off `tournament_id`. This serves Euro, Copa, UCL, etc. with zero DDL change.

**Tables (PK = `id uuid` unless noted):**

- **users** — `email citext unique`, `display_name`, `auth_provider`, `auth_subject` (or `password_hash`), `timezone`, `locale`, `created_at`, `updated_at`.
- **tournaments** — `slug unique`, `name`, `sport` (default `football`), `start_date`, `end_date`, `status` (`upcoming|group_stage|knockout|completed`), `format_config jsonb` (groups, rounds, team count, advancement rules), `scoring_config jsonb` (points per round/exact-score/bonus), `created_at`, `updated_at`.
- **teams** — `name`, `short_name`, `country_code`, `crest_url`, `external_ref` (provider id), `created_at`. Global, reused across tournaments.
- **tournament_teams** — `tournament_id fk`, `team_id fk`, `group_label`, `seed`, `unique(tournament_id, team_id)`. The N:M bridge teams↔tournaments.
- **favorite_teams** — `user_id fk`, `team_id fk`, `created_at`, `unique(user_id, team_id)`.
- **fixtures** (match cache) — `tournament_id fk`, `external_ref` (provider match id, unique per provider), `stage`, `round_key` (generic id from `format_config`), `group_label`, `home_team_id`/`away_team_id` (nullable until known), `home_placeholder`/`away_placeholder` (e.g. "Winner Group A"), `kickoff_at timestamptz`, `venue`, `status` (`scheduled|live|finished|postponed|cancelled`), `home_score`/`away_score`, `home_score_et`/`away_score_et`/`home_pens`/`away_pens` (knockout), `winner_team_id`, `raw jsonb` (cached payload), `fetched_at`, `updated_at`.
- **brackets** (a user's entry for a tournament) — `user_id fk`, `tournament_id fk`, `name`, `status` (`draft|submitted|locked|scored`), `submitted_at`, `total_score int` (denormalized cache), `created_at`, `updated_at`.
- **bracket_picks** (predictions inside a bracket) — `bracket_id fk`, `fixture_id fk nullable`, `round_key`, `pick_type` (`match_result|match_score|advancing_team|group_position|champion|golden_boot`), `predicted_home_team_id`/`predicted_away_team_id`, `predicted_winner_team_id`, `predicted_home_score`/`predicted_away_score`, `predicted_team_id` (generic single-team pick), `points_awarded int nullable`, `is_correct bool nullable`, `scored_at`, `created_at`, `updated_at`.
- **leagues** (private friend leagues) — `tournament_id fk`, `name`, `owner_user_id fk users`, `invite_code unique`, `visibility` (`private|public`, default private), `scoring_config jsonb nullable` (overrides tournament scoring), `max_members`, `created_at`, `updated_at`.
- **league_memberships** — `league_id fk`, `user_id fk`, `role` (`owner|admin|member`), `bracket_id fk nullable` (entry used in this league), `joined_at`, `unique(league_id, user_id)`.
- **briefings** (generated pre-match briefings + status) — `fixture_id fk`, `tournament_id fk` (denorm), `user_id fk nullable` (null = generic, set = personalized), `type` (`pre_match|post_match|daily`), `status` (`pending|generating|ready|failed`), `content text`, `content_format` (default `markdown`), `model`, `thread_id text nullable` (the LangGraph thread that produced it), `generated_at`, `error`, `created_at`, `updated_at`.
- **conversations** (app users ↔ LangGraph threads) — `user_id fk`, `thread_id text unique` (the checkpointer's thread_id; keep <255 chars, use a UUID), `tournament_id fk nullable`, `title`, `last_message_at`, `metadata jsonb`, `created_at`, `updated_at`.

**ERD-style relationships:** `users` 1—N `brackets`, `favorite_teams`, `league_memberships`, `conversations`, and owns N `leagues`. `tournaments` 1—N `fixtures`, `tournament_teams`, `brackets`, `leagues`. `teams` N—M `tournaments` via `tournament_teams`, and are referenced by `favorite_teams`, `fixtures`, `bracket_picks`. `brackets` 1—N `bracket_picks`; a bracket is linked into a league through `league_memberships.bracket_id`. `leagues` 1—N `league_memberships`. `fixtures` 1—N `briefings` and are referenced by `bracket_picks`. **`conversations.thread_id` is the logical join to the checkpointer's `checkpoints.thread_id`** — keep it as a string, **no cross-schema FK** (the checkpointer owns its tables/migrations).

### 4. How bracket scoring data is stored

- **Rules** live in `tournaments.scoring_config` (JSONB), e.g. points per correct group result vs. round-of-16 vs. final, exact-score bonus, champion bonus. A league may override via `leagues.scoring_config`. Keeping rules as JSONB (not columns) keeps the engine tournament-agnostic.
- **Per-pick results**: a scoring job compares each `bracket_picks` row against the settled `fixtures` outcome and writes `points_awarded` + `is_correct` + `scored_at`. This preserves a full audit of how each point was earned.
- **Bracket total**: `brackets.total_score` is a denormalized cache recomputed on each scoring run, so a league leaderboard is just `SELECT ... ORDER BY total_score DESC` joining `league_memberships → brackets` — no recomputation at read time.

### Recommendations summary

1. App layer: **SQLAlchemy 2.0.51 async + asyncpg 0.31.0**; stay off 2.1 beta. 2. **Alembic 1.18.5**, async template. 3. SQLModel 0.0.39 optional only. 4. Checkpointer in the **same instance, `langgraph` schema** via `search_path` (no Python `schema=` arg), separate psycopg3 pool. 5. **Config-driven `tournaments`** (JSONB format + scoring) so the schema fits any knockout/group event. 6. Scoring = JSONB rules + per-pick `points_awarded`/`is_correct` + denormalized `brackets.total_score`.

---

### Open questions from this stream

- Whether/when to migrate to SQLAlchemy 2.1 once it leaves beta - this is gated on SQLModel relaxing its <2.1 pin if SQLModel is used; if you go pure SQLAlchemy you can adopt 2.1 sooner.
- Exact schema-isolation behavior of the installed langgraph-checkpoint-postgres version: the Python AsyncPostgresSaver constructor shows no schema= parameter (only conn/pipe/serde), so search_path is the documented-by-community workaround rather than an official API - verify against the source of the exact version you deploy (the langchain-ai/docs issue #465 requesting official schema docs was still open).
- Third-party performance benchmark claims (e.g. blog claims of 'asyncpg 45% faster' or 'async Alembic 15x faster') could not be cross-checked against primary sources and were excluded from recommendations.
- Whether briefings should be generated/stored per-user (personalized) or shared per-fixture - schema supports both via a nullable user_id, but the product decision affects unique constraints and cache hit rate.
- Whether leagues should ever span multiple tournaments (season-long) - current proposal scopes a league to one tournament_id for MVP simplicity; multi-tournament leagues would need a league_tournaments join.