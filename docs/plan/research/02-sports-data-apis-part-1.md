# Research: SPORTS DATA APIs (part 1) — fixtures/lineups/live/standings providers for World Cup 2026

> Cited synthesis from the Pitch IQ research workflow (run 2026-06-30). Versions/URLs are primary-source-verified; see open questions for unresolved items.

**Executive summary:** For FIFA World Cup 2026, three providers stand out. API-FOOTBALL (api-sports.io v3) explicitly covers the tournament under league id 1, season 2026, exposing fixtures, lineups, live events/minute/score, standings/groups, head-to-head and player stats from a single REST API; its free tier is 100 requests/day (10 req/min) with ALL endpoints unlocked, paid plans run $19/$29/$39/mo, and live data refreshes every ~15s via polling. football-data.org (v4) confirms World Cup (competition code WC) is in its FREE 12-competition tier, but free is fixtures/results/standings with DELAYED scores; live scores need a €12/mo add-on and lineups/goal-detail need the €29/mo Deep Data add-on, and attribution is required. SportMonks (v3) covers WC2026 (season id 26618) richly including xG/predictions/bracket with <15s livescores, but the World Cup is NOT in its free plan (free = 2 minor leagues only); dedicated WC plans are €69 and €129/mo. None of the three offer a public websocket/push feed — all are polling; only enterprise Sportradar (official FIFA data partner) offers real-time push. Preliminary recommendation: API-FOOTBALL as primary (best price/coverage balance, full live state, single API), football-data.org free tier as a zero-cost fallback for fixtures/standings, and SportMonks if xG/predictions are required.

---

## Sports Data APIs for FIFA World Cup 2026 — Fixtures, Lineups, Live, Standings

The tournament is live (11 Jun–19 Jul 2026, 48 teams, 12 groups, 104 matches). Three providers are realistic for a fixtures/live/standings build: **API-FOOTBALL**, **football-data.org**, and **SportMonks**. Below, the most important question — *does it actually cover WC2026?* — is answered first for each.

### 1) API-FOOTBALL (api-sports.io)

**WC2026 coverage: YES, explicitly.** Per API-FOOTBALL's own [World Cup 2026 guide](https://www.api-football.com/news/post/fifa-world-cup-2026-guide-to-using-data-with-api-sports), the tournament is `league=1`, `season=2026`. `GET /fixtures?league=1&season=2026` returns all 104 matches (each with fixture id, UTC date/time, venue, status); matches are populated as the tournament progresses. Standings/groups: `GET /standings?league=1&season=2026`; the 48 teams: `teams?league=1&season=2026`. Coverage for the competition includes fixtures with events, lineups, fixture & player statistics, standings, players, top scorers/assists/cards, injuries, predictions and odds ([coverage page](https://www.api-football.com/coverage)).

**Data available:** fixtures/schedule, lineups (XI + formations), live state (events, minute, score, added time), standings/group tables, head-to-head, player stats — all from one API.

**Auth & base URL:** Direct at `https://v3.football.api-sports.io` with header `x-apisports-key: <KEY>`; a RapidAPI mirror exists at `https://api-football-v1.p.rapidapi.com/v3` using `x-rapidapi-key` + `x-rapidapi-host` ([docs](https://api-sports.io/documentation/football/v3)).

**Fixtures response shape (key fields):** `response[].fixture` → `id, referee, timezone, date, timestamp, periods{first,second}, venue{id,name,city}, status{long,short,elapsed,extra}`; plus `league{id,season,round}`, `teams{home,away}` (with `winner`), `goals{home,away}`, and `score{halftime,fulltime,extratime,penalty}`.

**Live/events shape:** `GET /fixtures/events?fixture={id}` returns `time{elapsed,extra}`, `team`, `player{id,name}`, `assist{id,name}`, `type` (Goal/Card/subst/Var), `detail`, `comments`. During play, `status.short` (e.g. `1H/HT/2H/ET/FT`), `status.elapsed` (current minute) and `time.extra` (added/injury minutes, e.g. 90+4 → elapsed 90, extra 4) drive logic. You can pull all in-play matches with `?live=all` or filter `?live=1` ([live docs notes](https://api-sports.io/documentation/football/v3)).

**Free tier & pricing:** Free = **100 requests/day, 10 req/min, ALL endpoints unlocked**. Paid (direct): **Pro $19/mo (7,500/day, 300/min), Ultra $29/mo (75,000/day, 450/min), Mega $39/mo (150,000/day, 900/min)** ([ratelimit doc](https://www.api-football.com/news/post/how-ratelimit-works); cross-checked by [Highlightly](https://highlightly.net/blogs/best-football-apis-in-2026)).

**Latency/polling:** live endpoints refresh **every ~15 seconds**; recommended polling is **1 call/min for in-progress fixtures**, 1/day otherwise ([save-calls guide](https://www.api-football.com/news/post/how-to-save-calls-to-the-api)). No public websocket/push.

**ToS:** Logos served from `media.api-sports.io`; redistribution/display limits live in their terms (verify before resale).

### 2) football-data.org

**WC2026 coverage: YES, and on the FREE tier.** The [coverage page](https://www.football-data.org/coverage) lists "Worldcup" among the 12 free competitions (with Champions League, the big-5 European leagues, etc.). Access via competition code **`WC`**: `https://api.football-data.org/v4/competitions/WC/matches` ([v4 match docs](https://docs.football-data.org/general/v4/match.html)).

**Data available:** fixtures/results, standings (group tables, TOTAL/HOME/AWAY), head-to-head (`/matches/{id}/head2head`), and — on paid tiers — lineups, goal scorers, bookings, substitutions, squads. Match fields: `id, utcDate, status, minute, injuryTime, matchday, stage, group, score{winner,duration,fullTime,halfTime}`, plus `homeTeam/awayTeam` with `coach, formation, lineup, bench, statistics`, and `goals/bookings/substitutions/penalties/referees` arrays.

**Status enum (useful for live):** `SCHEDULED, TIMED, IN_PLAY, PAUSED, FINISHED, SUSPENDED, POSTPONED, CANCELLED, AWARDED`.

**Auth & base URL:** `https://api.football-data.org/v4`, header **`X-Auth-Token`**. Unauthenticated = 100 req/24h (only area + competitions list) ([policies](https://docs.football-data.org/general/v4/policies.html)).

**Free tier & pricing:** Free = **10 req/min, 12 competitions, but DELAYED scores** (not real-time). Live scores need the **€12/mo Livescores** add-on; lineups/scorers/cards/squads need **€29/mo Deep Data**; **Statistics €15**, **Odds €15**. Full tiers: Standard €49 (30 comps, 60/min), Advanced €99 (50 comps, 100/min), Pro €199 (100 comps, 120/min) ([pricing](https://www.football-data.org/pricing)).

**Latency:** free is delayed; even paid is polling (no websocket). **ToS:** attribution required — "Football data provided by the Football-Data.org API" — per [thestatsapi summary](https://www.thestatsapi.com/blog/thestatsapi-vs-football-data-org) (verify exact terms directly).

### 3) SportMonks

**WC2026 coverage: YES, but NOT free.** Season id **26618**; SportMonks uses standard endpoints with filters/includes rather than tournament-specific routes ([WC guide](https://www.sportmonks.com/blogs/world-cup-2026-api-guide-coverage-endpoints-data-types/)). Stage ids are published (Group 77478590 … Final 77479090). Core endpoints: `/fixtures`, `/livescores/inplay`, `/standings/seasons/{seasonId}`, `/expected/fixtures` (xG). Key includes: `participants, scores, events, lineups, statistics, state, venue, periods, formations, referees`.

**Free tier:** the World Cup is **not** included — the free plan covers only Danish Superliga + Scottish Premiership ([Highlightly](https://highlightly.net/blogs/best-football-apis-in-2026)). WC plans: **Special €69/mo (€55 yearly)** = fixtures, livescores, events, lineups, standings, squads, bracket; **All-In €129/mo (€103 yearly)** adds predictions, xG, Pressure Index, odds ([WC API page](https://www.sportmonks.com/football-api/world-cup-api/)).

**Auth & base URL:** `https://api.sportmonks.com/v3/football`, API token. **Latency:** livescores **<15s**; xG updates every couple of minutes. No public websocket on the WC pages.

### Other providers (noted, not deeply evaluated)
- **Highlightly** — WC2026 included, free 100 req/day, $9.49–$45.99/mo, adds video highlights + odds ([blog](https://highlightly.net/blogs/best-football-apis-in-2026)).
- **Sportradar** — official FIFA data partner with real-time **push feeds**, enterprise pricing ($500+/mo); the only one with true push.
- **TheSportsDB** ($9–$20/mo, ~2-min livescores), **SportsDataIO** (enterprise), **TheStatsAPI** ($50–$379/mo, includes xG), **KickoffAPI**, **live-score-api.com** — all viable but secondary.

### Comparison table

| | API-FOOTBALL | football-data.org | SportMonks |
|---|---|---|---|
| WC2026 covered | Yes (`league=1, season=2026`) | Yes, code `WC`, **free tier** | Yes (`season=26618`), **paid only** |
| API / base | v3 `v3.football.api-sports.io` | v4 `api.football-data.org/v4` | v3 `api.sportmonks.com/v3/football` |
| Auth | `x-apisports-key` (or RapidAPI) | `X-Auth-Token` | token |
| Fixtures/lineups/events/standings/H2H | All yes | Yes (lineups/events = paid add-on) | All yes (via includes) |
| Player stats / xG | Stats yes; no xG | Stats add-on; no xG | Stats + xG (All-In) |
| Free tier | 100/day, 10/min, all endpoints | 10/min, 12 comps, **delayed** | WC not free |
| Live latency | ~15s polling | delayed (free) / polling | <15s polling |
| Websocket/push | No | No | No (public) |
| Entry paid | $19/mo Pro | €12 livescores add-on | €69/mo Special |

### Recommendations
1. **Primary: API-FOOTBALL.** Best balance — full WC2026 coverage, complete live match state (minute/score/added time/events), lineups, standings/groups and H2H in one cheap API; free tier unlocks everything for prototyping, and $19–$39/mo handles matchday traffic. Build polling at ~1 req/min per in-progress fixture.
2. **Fallback: football-data.org (free).** Zero-cost source of truth for fixtures, results and group tables (code `WC`), useful for reconciliation/redundancy. Accept delayed scores on free and add attribution.
3. **Add SportMonks** only if xG, predictions, Pressure Index or richer bracket data are product requirements (€69–€129/mo).
4. **Architecture:** all three are polling — design a poller (fast cadence during live windows, slow otherwise) with caching; reserve real-time push for an enterprise Sportradar integration if sub-second updates ever become a hard requirement.

---

### Open questions from this stream

- football-data.org's full Terms of Service redistribution/caching rules were not readable from the v4 policies page excerpt (returned a partial excerpt); the attribution requirement was confirmed only via a third-party blog (thestatsapi.com), so the exact wording and any redistribution limits should be verified directly in football-data.org's ToS before commercial use.
- API-FOOTBALL's official World Cup 2026 guide and pricing/coverage pages return HTTP 403 to automated fetching; league=1/season=2026, the 100/day-10/min free limit, and $19/$29/$39 plan prices were taken from API-FOOTBALL's own ratelimit/guide pages as surfaced by search and cross-checked against the Highlightly blog, but were not directly machine-read from the live pricing page.
- SportMonks World Cup LEAGUE id (reported as 732 by search) was not shown on the official world-cup-api page; only SEASON id 26618 and the stage ids were confirmed in the SportMonks blog. Confirm the league id via the SportMonks /leagues endpoint with a token.
- No provider among API-FOOTBALL, football-data.org and SportMonks was confirmed to offer a public websocket/push feed; whether any offers a private/enterprise push channel for WC2026 (vs. Sportradar) is unconfirmed.
- Exact field-level JSON for API-FOOTBALL /fixtures/events (e.g., whether VAR sub-types and assist nulls behave as documented for WC2026 specifically) was inferred from general v3 docs/search rather than read from a live WC2026 response.