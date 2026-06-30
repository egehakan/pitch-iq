# Research: SPORTS DATA APIs (part 2) — ODDS / WIN-PROBABILITY + premium providers

> Cited synthesis from the Pitch IQ research workflow (run 2026-06-30). Versions/URLs are primary-source-verified; see open questions for unresolved items.

**Executive summary:** For a cost-conscious win-probability signal for Pitch IQ's prediction critic, The Odds API (the-odds-api.com, v4) is the clear primary source. It explicitly carries World Cup 2026 under sport key `soccer_fifa_world_cup`, returns 3-way (home/draw/away) decimal prices from 50+ bookmakers including the sharp book Pinnacle, and lets you derive fair implied probabilities by inverting and de-vigging the odds. Its free tier is 500 credits/month (no card) and paid tiers start at $30/month for 20,000 credits — orders of magnitude cheaper than the alternatives, and more than enough for the entire 104-match tournament. Sportradar offers a purpose-built Probabilities API that returns 3-way win/draw/loss probabilities directly (pre-match and live, updated through the match) plus official low-latency odds feeds, but it is B2B-only with no public pricing (third-party estimates put the floor at ~$10,000+/month), requires a signed commercial agreement, mandates a "powered by Sportradar" logo, and — critically — its terms prohibit use "for any prediction market, trading platform, financial product or similar offering" without prior written consent, which directly implicates a prediction product like Pitch IQ. Recommendation: build the critic on odds-derived no-vig consensus (anchored on Pinnacle/Betfair) from The Odds API as the market benchmark, and treat Sportradar as a later upgrade only if you need official, branded, sub-second live probabilities at enterprise scale and clear the prediction-market clause with their legal team.

---

## Odds / Win-Probability Sourcing for Pitch IQ's Prediction Critic

### What the critic actually needs
A "win-probability signal" for a prediction critic is best built from a **de-vigged market line** (the consensus of sharp bookmakers), which is the most calibrated public estimate of true match probability. Two providers cover this for World Cup 2026: a cheap aggregator ([The Odds API](https://the-odds-api.com/)) that returns raw bookmaker prices you convert yourself, and a premium feed ([Sportradar](https://developer.sportradar.com/odds/reference/probabilities-overview)) that returns ready-made probabilities. The conversion math is trivial, so the aggregator gets you 95% of the value at ~0.3% of the cost.

### The Odds API (the-odds-api.com)

**Coverage.** World Cup 2026 is explicitly carried under sport key **`soccer_fifa_world_cup`**, returning live and upcoming matches ([World Cup odds page](https://the-odds-api.com/sports/fifa-world-cup-odds.html)). Soccer markets include the **3-way `h2h`** (home / away / **draw** — exactly what you need), plus `spreads` (handicap), `totals` (over/under), `btts`, `outrights` (tournament winner), and player props.

**API shape (v4).** Base URL `https://api.the-odds-api.com`; auth is a simple **`apiKey` query parameter** ([v4 docs](https://the-odds-api.com/liveapi/guides/v4/)). The core call:

```
GET /v4/sports/soccer_fifa_world_cup/odds/?apiKey=KEY&regions=eu&markets=h2h&oddsFormat=decimal
```

Response is an array of events, each:

```json
{
  "id": "...", "sport_key": "soccer_fifa_world_cup",
  "commence_time": "2026-06-30T19:00:00Z",
  "home_team": "Netherlands", "away_team": "Japan",
  "bookmakers": [{
    "key": "pinnacle", "title": "Pinnacle", "last_update": "...",
    "markets": [{ "key": "h2h", "outcomes": [
      {"name":"Netherlands","price":1.97},
      {"name":"Japan","price":3.6},
      {"name":"Draw","price":3.6}]}]
  }]
}
```

Quota is tracked via response headers `x-requests-remaining`, `x-requests-used`, `x-requests-last`. **Cost = markets × regions** credits; `GET /v4/sports` and `/events` are free.

**Deriving win-probability.** Request `oddsFormat=decimal`; raw implied probability is `1/price`. The three outcomes sum to >1 (the overround/vig), so normalize: `p_i = (1/price_i) / Σ(1/price_j)`. Anchor on the **sharpest book** for calibration — and despite a third-party blog claiming otherwise ([oddspapi](https://oddspapi.io/blog/odds-api-pricing-2026-comparison/)), the official bookmaker list confirms **Pinnacle is included (EU region, key `pinnacle`)** alongside Betfair Exchange ([bookmaker list](https://the-odds-api.com/sports-odds-data/bookmaker-apis.html)). Betfair Exchange (multiple regions) and Bet365 (AU) are also available; 50+ sources total.

**Latency.** Featured markets refresh **60s pre-match / 40s in-play**; betting exchanges 20s/10s; the interval ramps down starting 6h before kickoff ([update intervals](https://the-odds-api.com/sports-odds-data/update-intervals.html)).

**Pricing.** Free **500 credits/month, no card**; then **$30/mo (20K)**, **$59/mo (100K)**, **$119/mo (5M)**, **$249/mo (15M)** — all tiers include every sport, book, market and historical odds ([pricing](https://the-odds-api.com/)), cross-checked against the [oddspapi 2026 comparison](https://oddspapi.io/blog/odds-api-pricing-2026-comparison/). At 1 credit per (h2h × eu) call, the 104-match tournament costs almost nothing even polling live.

**ToS.** Commercial use in "websites, mobile apps, dashboards, analytical tools" is **explicitly permitted**; you may **not** resell/redistribute the data as a standalone data product, and responsible-gambling messaging ("Gamble Responsibly. 18+") is encouraged where odds are shown ([terms](https://the-odds-api.com/terms-and-conditions.html)). No "powered by" branding requirement.

### Sportradar

**What it adds.** Sportradar's **Probabilities API (v1)** returns **3-way win/draw/loss probabilities directly** — pre-match and live, with a dynamic timeline updating through the match — so no de-vig math is needed ([Probabilities overview](https://developer.sportradar.com/odds/reference/probabilities-overview)). Soccer's live feed sits at `https://api.sportradar.com/soccer-extended-probabilities/{access_level}/v4/{language_code}/schedules/live/probabilities.{format}` ([live probabilities](https://developer.sportradar.com/soccer/reference/soccer-extended-live-probabilities)). It also sells Odds Comparison Prematch / Live / Player Props / Futures feeds with official-grade latency and the deepest coverage. Auth is the **`x-api-key` header** (40-char key) with `accept: application/json`, base pattern `api.sportradar.com/{sport}/{access-level}/{version}/{language}/{endpoint}.{format}` ([auth](https://developer.sportradar.com/getting-started/docs/authentication)).

**Access & licensing weight.** A **30-day free trial** exists but is non-commercial/internal-eval only — trial keys **cannot publish or display** data. Production requires a **signed Order Form**; it is B2B-only with **no public pricing**, and third-party reviews put the floor around **$10,000+/month** ([review](https://sportsapipro.com/reviews/sportradar), [SharpAPI](https://sharpapi.io/compare/sportradar-alternative)). The [Terms & Conditions](https://developer.sportradar.com/sportradar-updates/page/terms-and-conditions) impose three constraints that matter for Pitch IQ: a **"powered by Sportradar" logo is mandatory** (§2.12); gambling/betting use needs **express written approval** (§2.10, §8); and use **"for any prediction market, trading platform, financial product or similar offering"** requires prior written consent that may be withheld (§2.1). A prediction product plausibly triggers §2.1 — clear this before spending.

### Comparison

| | The Odds API | Sportradar |
|---|---|---|
| WC 2026 coverage | Yes (`soccer_fifa_world_cup`) | Yes (global soccer) |
| Win-prob | Derive (1/odds, de-vig) | **Native 3-way probabilities** |
| Markets | h2h/3-way, totals, spreads, btts, outrights, props | 3-way, totals, props, futures, full odds comparison |
| Auth | `apiKey` query param | `x-api-key` header |
| Free tier | 500 credits/mo, no card | 30-day trial, non-commercial only |
| Paid entry | **$30/mo (20K credits)** | **~$10k+/mo (no public price)** |
| Latency | 60s pre / 40s live | Lower (official feed) |
| ToS friction | Low; commercial OK | High: signed deal, logo, prediction-market clause |

### Recommendation
Build the critic on **The Odds API**: pull `soccer_fifa_world_cup` `h2h` for the `eu` region in decimal format, anchor on **Pinnacle** (fall back to Betfair Exchange or a multi-book median), and **de-vig** to fair home/draw/away probabilities. Use that market line as the **benchmark the in-house model is scored against** (Brier/log-loss vs market), optionally blending. This is cheap ($0–$30/mo), well-calibrated, and ToS-clean. **Skip Sportradar for now** — its native probabilities are nicer to consume but cost ~300× more, require a signed agreement and "powered by Sportradar" branding, and its prediction-market clause may not even permit Pitch IQ's use case. Revisit Sportradar only if you later need official, branded, sub-second live probabilities at scale, and clear §2.1/§2.10 with their legal team first.

---

### Open questions from this stream

- Exact Sportradar pricing for the Soccer Probabilities / Odds Comparison feeds is not published; the ~$10,000+/month floor is a third-party estimate (sportsapipro.com, sharpapi.io), not an official quote — a sales call is required to confirm the real cost for World Cup-scoped soccer coverage.
- Whether Pitch IQ's 'prediction critic' use of Sportradar data would be deemed a prohibited 'prediction market / trading platform / financial product' under T&C Section 2.1, or acceptable internal analytics — must be clarified with Sportradar legal before any commitment.
- Sportradar's Probabilities API soccer response shape (exact field names, whether probabilities are 0-1 decimals or percentages, live update frequency in seconds) could not be read from the public docs without authenticated 'Try It' access; needs a trial key to confirm.
- The claim that Sportradar's 3-way probabilities are derived specifically from 'aggregated US sportsbooks' comes from a marketplace/search summary, not the primary reference page — confirm the underlying odds sources and how they map to soccer/World Cup.
- The Odds API does not publish hard concurrent rate-limit numbers (only a 429 on exceed); real-world throughput under heavy in-play polling during simultaneous World Cup matches should be load-tested.
- Other providers (SportsGameOdds, OpticOdds, OddsPapi) were only lightly surveyed via a third-party comparison; if Pinnacle-anchored fair odds or 250+ books are needed, they warrant a direct primary-source pass.