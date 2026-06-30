# 09 — Risks & Open Questions

> Purpose: the consolidated risk register (likelihood × impact × concrete mitigation) and the numbered sign-off questions for Pitch IQ, derived from `research/canonical-spec.md` §9, `research/09-decision-memo.md` §7–§8, and `research/08-verification-verdicts.md`.

**Status:** for sign-off · **Date:** 2026-06-30 · Authority: if anything here contradicts `research/canonical-spec.md`, the spec wins.

Two layers are kept strictly separate throughout:
- **Runtime** = LangGraph behavior *inside the product* (what the shipped app does).
- **Build** = Claude Code dynamic-workflow orchestration used *to build the product* (wf-01…wf-08).

Most risks below are Runtime/Ops/Legal; the build layer appears explicitly under R12 (version drift) and R13 (workflow token spend).

---

## 1. How to read this register

**Likelihood / Impact scale:** Low / Med / High. **Priority** = informal product of the two (Critical = High×High or a launch-blocker; High; Med; Low).

```
Impact ▲
 High │  R3 R7        R1
      │  R6 R5  R2 R4 R12
 Med  │  R8 R9  R10 R11 R13
      │
 Low  │              R14
      └─────────────────────▶ Likelihood
         Low      Med     High
```

Every risk that asserts a fast-moving library/API fact carries a source URL. Anything not adversarially confirmed is escalated to a numbered Open Question in §3 rather than asserted here.

---

## 2. Risk register

| ID | Risk | Layer | Likelihood | Impact | Priority | Concrete mitigation (spec-faithful) |
|---|---|---|---|---|---|---|
| **R1** | **Data-API reliability + cost.** API-Football free tier (`$0/mo`, **100 req/day + 10 req/min**) cannot sustain 15-second live polling; production live needs **Pro $19/mo (7,500/day)**. Polling spend balloons if every fixture is polled all day; coverage flags are `true` but "availability may vary match to match." | Runtime / Ops | High | High | **Critical** | Budget **API-Football Pro $19/mo** as the live floor (see budget ceiling, Q11). Poll only inside live windows: `poll_live()` interval = `LIVE_POLL_SECONDS=60`, active **only while a relevant fixture is in the `live` status window**. `CachingProvider` = TTL cache (fixtures/standings 6–24h, odds ≤6h pre-match) + token-bucket rate limit per provider. **football-data.org v4** (`WC`, header `X-Auth-Token`) as cold fallback/reconciliation; 429 → exponential backoff → failover. Design tools to tolerate missing lineups/events (`get_lineups` may return partial). Pricing: https://www.api-football.com/pricing · WC guide: https://www.api-football.com/news/post/fifa-world-cup-2026-guide-to-using-data-with-api-sports |
| **R2** | **Seasonal demand window.** Tournament demand is a weeks-long spike (WC2026 knockouts now → final ~mid-July), then collapses. Over-provisioning wastes money; under-provisioning fails during the one window that matters; idle infra burns cost between tournaments. | Ops | High | Med | High | Architecture is **config-driven + provider-abstracted** so the same engine re-points at the next event with **zero schema DDL** (only new `tournaments` rows + provider id mapping) — longevity without a rewrite. Stateless FastAPI **web** tier scales horizontally (scheduler disabled there); the **single** `RUN_SCHEDULER=true` worker (1 replica) is the only stateful-cadence process and stays at 1. Between tournaments: scale web to ~0–1, pause `poll_live()`/`nightly_sync()`, drop paid API tiers back to free. Managed Postgres (Neon/RDS) scales independently. Cost-control the spike via cheap models on hot paths + aggressive caching (R1, R4). |
| **R3** | **Prediction accuracy & the hard "never state a prediction as fact" rule.** A naive or over-confident prediction stated as certainty is both a credibility and a (soft) legal/trust risk; users must always see probabilities as *hedged*, not facts. | Runtime | Med | High | **Critical** | **Defense-in-depth, three independent layers** (see §2.1): (1) **Generator→critic loop** in `app/graph/subgraphs/prediction.py` — `gen_prediction` → `critic` → conditional loop back (≤2 rounds) → `finalize`; critic rubric: probabilities valid + sum→1, within a sane band of the **no-vig market line** (de-vig `p_i=(1/d_i)/Σ(1/d_j)`, anchor **Pinnacle**), rationale cites form not vibes, flags favorite-bias; verdict ∈ {`pass`,`revise`}. (2) **UI framing** — predictions render as probabilities/ranges with explicit hedging copy, never "X will win"; odds surfaced ⇒ "18+ Gamble Responsibly". (3) **Groundedness evals** — qa_agent system prompt forbids unverified facts (must call a tool for any live claim); `openevals 0.2.0` `HALLUCINATION_PROMPT`/`RAG_GROUNDEDNESS_PROMPT` + deterministic number/entity-in-source check; **gate: groundedness pass-rate ≥ 0.95, Brier ≤ market+0.02**. |
| **R4** | **LLM + workflow token cost.** Chat is the hot path; an expensive model on every turn, plus eval LLM calls per commit, blows the seasonal budget. | Runtime / Build | Med | Med | Med | **Cheap models on hot paths** via the 3-tier convention in `app/graph/llm.py` (all via `init_chat_model`): `MODEL_ROUTER` = small/fast (router, chitchat), `MODEL_AGENT` = mid (ReAct Q&A, briefing sections), `MODEL_CRITIC` = reasoning (prediction critic, briefing plan). One cheap structured-output classifier (router) gates the expensive specialists. Cache aggressively (provider cache cuts tool round-trips → fewer agent steps). Evals use **`LANGSMITH_TEST_CACHE`** so the eval suite is not re-billed per commit (nightly/PR-gated, not every push). Build layer: workflow model routing — mechanical stages on Sonnet, design/SSE/adversarial/eval stages on Opus; **cost-control rule = run each large workflow on a one-unit slice first** to gauge spend before full fan-out (≤16). |
| **R5** | **LangGraph token-stream v3 is beta.** The official "event streaming" typed-projection API (`graph.astream_events(..., version="v3")`) is now *recommended for new apps* but the **v3 protocol is still beta** and may change. | Runtime | Med | Med | Med | **Ship on stable `graph.astream(..., stream_mode="messages")` with `version="v2"`** → `(message_chunk, metadata)`, filter `metadata["langgraph_node"]` to the user-facing node(s). Gate the v3 migration behind GA. Docs: https://docs.langchain.com/oss/python/langgraph/event-streaming |
| **R6** | **AI SDK full data-protocol broken for FastAPI.** The official FastAPI data-stream example has open, unresolved issues (vercel/ai #7496) — the byte-format-sensitive UI Message Stream "just doesn't work" against arbitrary Python backends. | Runtime | High | Med | High | MVP uses the **plain-text protocol**: `useChat({ transport: new TextStreamChatTransport({ api: '/api/chat' }) })` behind the Next.js Route Handler proxy (`app/api/chat/route.ts`). Trade-off accepted: text protocol drops tool-call/usage/finish metadata. Upgrade to `DefaultChatTransport` + UI Message Stream (`x-vercel-ai-ui-message-stream: v1`, `data:{JSON}` parts → `[DONE]`) only when the UI needs structured tool/status parts and #7496 is resolved. Issue: https://github.com/vercel/ai/issues/7496 · Transport docs: https://ai-sdk.dev/docs/ai-sdk-ui/transport |
| **R7** | **APScheduler double-fires under multi-worker Uvicorn.** In-process `AsyncIOScheduler` under N uvicorn workers fires each job N times → duplicate briefings / duplicate scoring. | Runtime / Ops | High | High | **Critical** | **Single dedicated scheduler process** = same FastAPI image with `RUN_SCHEDULER=true`, **1 replica**, owns APScheduler + poller; the web tier runs with the scheduler **disabled**. Jobs use explicit `id` (`briefing:{fixture_id}`) + `replace_existing=True`; persistent `SQLAlchemyJobStore` on the same Postgres survives restarts. If horizontal scheduler scaling is ever needed → Postgres advisory-lock leader election. **APScheduler pinned 3.11.3 (NOT 4.x alpha).** https://github.com/agronholm/apscheduler |
| **R8** | **`interrupt()` re-runs the node from its top on resume.** On `Command(resume=...)`, the interrupting node re-executes from the start; non-idempotent code before `interrupt()` causes double side effects (e.g. double bracket lock). | Runtime | Med | Med | Med | In `app/graph/subgraphs/bracket_ops.py`: keep `confirm` node **idempotent**, put all consequential side effects **after** `interrupt(summary)`, keep **deterministic interrupt order**, and **never bare-`except`** around `interrupt()`. `apply_change` (lock/submit) is the only consequential write. Use `durability="sync"` for this run. `interrupt()`+`Command(resume=...)` is the current, non-deprecated HITL API (static breakpoints are debug-only). https://docs.langchain.com/oss/python/langgraph/interrupts |
| **R9** | **Checkpointer / app-schema collision + psycopg misconfig.** LangGraph checkpoint tables and the app ORM share one Postgres instance; name/transaction-mode collisions or wrong pool settings corrupt checkpoints. | Runtime / Ops | Low | High | Med | **Isolate by schema**: checkpointer on the **`langgraph`** schema via psycopg3 `options='-c search_path=langgraph'` (the Python `AsyncPostgresSaver` has no `schema=` arg); app ORM on the **`app`** schema via asyncpg. **Two separate pools**: checkpointer psycopg3 (`autocommit=True`, `row_factory=dict_row`, `prepare_threshold=0`); app SQLAlchemy 2.0.51 async + asyncpg 0.31.0. `await checkpointer.setup()` **once** in `lifespan`. No cross-schema FK; join logically on `conversations.thread_id` ↔ `checkpoints.thread_id`. Ref: https://reference.langchain.com/python/langgraph.checkpoint.postgres/aio/AsyncPostgresSaver |
| **R10** | **Sports/odds legal exposure.** Surfacing odds + a "prediction critic" can implicate gambling/prediction-market clauses; Sportradar's T&C §2.1 bars use "for any prediction market…financial product" without consent; football-data.org redistribution/caching ToS for commercial use is unconfirmed. | Legal | Med | High | High | **Do not adopt Sportradar** (deferred: B2B ~$10k+/mo + the prediction-market clause). **Derive** win probabilities from **The Odds API v4** (de-vig, anchor Pinnacle); **never resell raw odds**. Show **"18+ Gamble Responsibly"** wherever odds are surfaced. **No betting/wagering** (explicit non-goal). Confirm football-data.org attribution + redistribution ToS before commercial use (Q15). Sportradar T&C: https://developer.sportradar.com/sportradar-updates/page/terms-and-conditions · Odds: https://the-odds-api.com/sports/fifa-world-cup-odds.html |
| **R11** | **Briefing freshness SLA misses.** Success criterion = briefing generated + stored **before kickoff for 100% of the user's relevant fixtures**; a failed/late scheduler job, provider 429, or LLM error breaks the headline promise. | Runtime / Ops | Med | Med | Med | `schedule_briefings()` adds a `'date'` job at `kickoff − BRIEFING_LEAD_HOURS` (=2) with stable id + `replace_existing=True`; `nightly_sync()` re-schedules. `briefings.status` state machine (`pending→generating→ready│failed`) + `error` column makes misses observable; failed/late → manual `POST /api/briefings/{fixture_id}/generate`. Single scheduler (R7) guarantees one briefing per fixture. LangSmith traces the headless subgraph run. |
| **R12** | **Bleeding-edge version drift.** Many pinned libs released within days of 2026-06-30 (langgraph 1.2.7, fastapi 0.138.2, ai 7.0.8, tailwind 4.3.2, APScheduler 3.11.3). Peer ranges (esp. `@ai-sdk/react 4.0.9` ↔ `ai@7.0.8`) and unverified pins (`agentevals 0.0.9`) may break. | Build | Med | High | High | Commit **exact lockfiles** (`uv.lock`, `pnpm-lock.yaml`). **CI smoke** = installs + lints pass (wf-01), plus an SSE-endpoint test and a graph `astream` test that fail fast on drift. **Verify peer ranges at install** (`@ai-sdk/react` ↔ `ai@7`). Unconfirmed pins escalated to Open Questions (Q12, Q13, Q16). Build rule: `verify peers at install`. |
| **R13** | **Build-workflow token spend (Claude Code).** Eight build workflows with fan-outs ≤16 + adversarial reviewers on Opus can run up a large build bill if launched at full fan-out blind. | Build | Med | Med | Med | Model routing: mechanical stages → Sonnet, design (wf-03/04) + SSE (wf-06) + adversarial reviewers + eval design (wf-08) → Opus. **Run each large workflow on a one-unit slice first** (one provider / one endpoint / one component) to gauge spend, then full fan-out. Concurrency cap ≤16 respected. Turn-by-turn for tightly-coupled/sign-off stages avoids wasted parallel work. |
| **R14** | **first-party `fastapi.sse.EventSourceResponse` claim unverified.** Research claimed FastAPI 0.138.2 ships a first-party SSE response; not adversarially confirmed. | Runtime | Low | Low | Low | **`sse-starlette 3.4.5` `EventSourceResponse` is the chosen, verified transport** (sets `text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`, keep-alive pings, disconnect handling). The first-party shim is irrelevant unless confirmed (Q14); no action needed for MVP. |

### 2.1 R3 deep-dive — defense-in-depth so predictions are never stated as fact

```mermaid
flowchart LR
  U[User asks for a prediction] --> GEN[gen_prediction\nProbabilities + scoreline + drivers]
  MKT[fetch_market\nOdds API de-vig p_i=(1/d_i)/Σ(1/d_j)\nanchor Pinnacle] --> CRIT
  GEN --> CRIT{critic\nverdict ∈ pass/revise}
  CRIT -- revise & round<2 --> GEN
  CRIT -- pass / round=2 --> FIN[finalize Prediction]
  FIN --> UI[UI framing:\nprobabilities + hedge copy,\nnever 'X will win';\n18+ if odds shown]
  UI --> EVAL[(Offline gate\nBrier ≤ market+0.02\ngroundedness ≥ 0.95)]
```

Layer 1 (critic loop) and Layer 2 (UI framing) protect every live response; Layer 3 (LangSmith evals) is the CI gate that keeps both honest over time. All three are independent — a regression in one is caught by another.

---

## 3. Open questions for sign-off (numbered decisions)

Each item is a decision with options, a recommended default, and why it matters. **Q1–Q6 are product/business decisions that need an explicit user answer before build; Q7 is a budget gate; Q8–Q16 are technical confirmations resolvable by a pre-build spike** (default given so the build is not blocked, but flag if a constraint applies).

### Product decisions (need user answer)

1. **OpenAI model snapshots for `MODEL_ROUTER` / `MODEL_AGENT` / `MODEL_CRITIC` (+ the eval judge model).** The spec mandates pinning concrete snapshot ids from OpenAI's current GPT-5.x line, but the **exact ids are unverified against OpenAI's live model list**. *Decision:* approve the snapshot-pinning policy and confirm whether cost or capability constraints should bias the tier choices. *Recommended default:* smallest/cheapest snapshot that passes routing macro-F1 ≥ 0.9 for `MODEL_ROUTER`; a reasoning snapshot for `MODEL_CRITIC`; pin all in `app/graph/llm.py` config + record the judge snapshot in LangSmith experiment metadata. *Why:* hot-path cost (R4) and calibration quality (R3) both ride on this.

2. ✅ **RESOLVED — Briefings: shared-per-fixture.** `briefings.user_id` NULL = shared (generated once per fixture); a personalized "bracket impact" overlay is layered client-side. (User chose the recommended default; keeps briefing token cost (R4) + scheduler load (R11) low.)

3. **Leagues: single-tournament vs season-long (multi-tournament).** Decides whether `leagues`/`league_memberships` are scoped to one `tournament_id` or span many. *Recommended default:* **single-tournament for MVP** (matches `leagues.tournament_id` as-is); season-long is a post-MVP config change. *Why:* changes scoring aggregation and leaderboard reads; cheaper to keep scoped now.

4. ✅ **RESOLVED — Hosting: Vercel + Railway + managed Postgres.** Next.js on Vercel; two Railway services from one image — FastAPI **web** (`RUN_SCHEDULER` off, scale N) + a single **worker** (`RUN_SCHEDULER=true`, 1 replica, owns APScheduler + poller); managed Postgres (Railway Postgres or Neon). Satisfies the single-scheduler invariant (R7) and seasonal scale-down (R2).

5. ✅ **RESOLVED — Auth: email/password JWT + Google OAuth in the MVP** (user override of the default). Email/password via PyJWT HS256 + pwdlib[argon2]; Google via **Authlib** authorization-code flow at `GET /api/auth/google/login` + `GET /api/auth/google/callback`, upserting users by `(auth_provider, auth_subject)` and issuing the same HS256 session JWT. `users.password_hash` becomes **nullable** (OAuth-only accounts). Adds `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/`OAUTH_REDIRECT_URI` env vars + a Google Cloud OAuth client. ⚠️ Pin `authlib` exact version at install (new technical confirmation, **Q17**).

6. **`EncryptedSerializer` scope.** At-rest encryption of checkpoint blobs via `LANGGRAPH_AES_KEY` — required (regulatory/PII) or optional? Also unclear whether it auto-activates only on LangSmith/Platform or also self-hosted when the key is set. *Recommended default:* **set `LANGGRAPH_AES_KEY` and enable `EncryptedSerializer`** if checkpoints may contain PII; otherwise leave optional. *Why:* compliance posture + a small write-path cost.

### Budget gate (need user answer)

7. ✅ **RESOLVED — Paid-API budget baseline ≈ $50–90/mo.** **API-Football Pro $19/mo** (live floor) + **The Odds API $30/mo** (20k credits) + **LangSmith Developer free** (~5k traces/mo); **football-data.org free** as cold fallback. Tune R1/R4 mitigations (polling cadence, eval cache, model tiers) to this envelope; revisit only if usage approaches the caps.

### Technical confirmations (resolvable by pre-build spike; default unblocks build)

8. **`langgraph` `durability` default + `ainvoke` wiring.** Modes are exit/async/sync; "async" is assumed default but not quoted from a rendered primary doc, and whether `durability=` is wired into `invoke/ainvoke` is tracked by issue #5741. *Default:* set `durability="sync"` **explicitly** for HITL/scoring runs regardless of the default. Confirm against the live signature in wf-05.

9. **`langchain.agents.create_agent` full signature.** `response_format`, `state_schema`, `context_schema`, pre/post-model hooks not pulled from primary reference. *Default:* confirm before wiring the ReAct `qa_agent` (wf-03); fall back to documented params only.

10. **Briefings personalization ⇒ already covered by Q2** (schema/cache impact). No separate technical spike beyond honoring the Q2 decision in the migration.

11. **OpenAI strict structured-output for the router** — confirm `with_structured_output(RouterDecision)` enforces the closed `Route` enum via OpenAI strict `json_schema` at the pinned snapshot (Q1). *Default:* assume supported; verify in the routing eval (macro-F1 ≥ 0.9 gate, wf-03).

12. **`@ai-sdk/react 4.0.9` ↔ `ai@7.0.8` peer pairing.** Pinned from the `latest` dist-tag but the compatible pair is unconfirmed. *Default:* **verify the peer range in `package.json` at install** (wf-07); adjust pin if peers conflict (R12).

13. **`agentevals 0.0.9` currency.** Carries a 2025-07-24 date that looks stale vs langsmith/openevals; trajectory eval may have folded into openevals. *Default:* confirm a newer release before pinning (wf-08); if dead, drop trajectory eval or move to openevals.

14. **First-party `fastapi.sse.EventSourceResponse` in 0.138.2.** Claimed but unverified. *Default:* **use `sse-starlette 3.4.5`** regardless (R14); confirm the import only as a future simplification.

15. **football-data.org redistribution/caching ToS for commercial use.** Only attribution was confirmed (third-party). *Default:* read the actual ToS before relying on it as a commercial fallback (ties to R10/R1); attribution shown either way.

16. **Sportradar pricing + prediction-market clause** — only relevant *if ever reconsidered*. *Default:* **deferred** (R10); no action unless a sales+legal call is commissioned.

17. **`authlib` currency + Google OAuth wiring (new — from Q5 resolution).** Google OAuth is now in the MVP. *Default:* pin `authlib` exact version at install; create a Google Cloud OAuth 2.0 client (authorized redirect = `OAUTH_REDIRECT_URI`); verify the Starlette/Authlib integration at the pinned FastAPI 0.138.2 (wf-01 deps + wf-06 auth endpoints).

---

## 4. Sign-off summary

- **Resolved at sign-off #0 (2026-06-30):** ✅ Q2 (briefings shared-per-fixture) · ✅ Q4 (Vercel + Railway + managed Postgres) · ✅ Q5 (email/password + Google OAuth) · ✅ Q7 (budget ≈ $50–90/mo). The Q5 choice adds Google OAuth (Authlib) to the MVP — folded into docs 00/01/04/CLAUDE + spec.
- **Still blocking before the dependent phase:** **Q1** (OpenAI snapshot ids → needed by wf-03) and **Q3** (leagues single- vs multi-tournament → needed by the schema migration); **Q6** (checkpoint encryption) defaults to optional. wf-01 (foundations) can start now regardless.
- **Non-blocking (spike-resolvable, defaults stand):** Q8–Q17 — each has a safe default so the critical path is not gated; flag back only if a default proves false at install/spike time (Q17 = new `authlib` confirmation from the Q5 resolution).
- **Critical risks to watch through launch:** R1 (API cost/reliability), R3 (predictions-as-fact), R7 (scheduler double-fire). Each has a concrete, spec-faithful mitigation already in the architecture.
