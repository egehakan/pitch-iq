"""The Odds API (v4) — `OddsProvider` implementation.

Pulls 3-way `h2h` decimal prices for the FIFA World Cup (`soccer_fifa_world_cup`),
anchors on the sharp book Pinnacle (EU region, key ``pinnacle``) and owns the
proportional de-vig math (`devig_three_way`, canonical-spec §4.2/§5).

Auth: ``apiKey`` is a **query** param (not a header). See docs/plan/03-data-and-apis §2.3.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.errors import AuthError, NotFound, ProviderError, RateLimitError
from app.providers.base import (
    MatchOdds,
    OddsProvider,
    TeamRef,
    WinProbabilities,
    devig_three_way,
)

_PROVIDER = "the_odds_api"
_SPORT_KEY = "soccer_fifa_world_cup"
_DEFAULT_BASE_URL = "https://api.the-odds-api.com"
_PREFERRED_BOOKMAKER = "pinnacle"
_DRAW_NAME = "Draw"


def _name_match(left: str | None, right: str | None) -> bool:
    """Case-insensitive *contains* match (either side may be the longer label)."""
    if not left or not right:
        return False
    lo, ro = left.strip().lower(), right.strip().lower()
    return lo in ro or ro in lo


class TheOddsApiProvider(OddsProvider):
    """`OddsProvider` backed by The Odds API v4."""

    def __init__(self, api_key: str, base_url: str = _DEFAULT_BASE_URL) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=15.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    # ── HTTP ─────────────────────────────────────────────────────────────────
    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        query = {**params, "apiKey": self._api_key}
        try:
            resp = await self._client.get(path, params=query)
        except httpx.HTTPError as exc:  # network / timeout / protocol
            raise ProviderError(f"the_odds_api request failed: {exc}") from exc

        status = resp.status_code
        if status == 429:
            raise RateLimitError("the_odds_api rate limit exceeded (429)")
        if status in (401, 403):
            raise AuthError(f"the_odds_api auth failed ({status})")
        if status == 404:
            raise NotFound("the_odds_api resource not found (404)")
        if status >= 400:
            raise ProviderError(f"the_odds_api returned HTTP {status}")

        try:
            return resp.json()
        except ValueError as exc:
            raise ProviderError("the_odds_api returned malformed JSON") from exc

    # ── matching helpers ─────────────────────────────────────────────────────
    def _find_event(
        self, events: list[dict[str, Any]], a: TeamRef, b: TeamRef
    ) -> dict[str, Any] | None:
        for event in events:
            home = event.get("home_team")
            away = event.get("away_team")
            ab = _name_match(a.name, home) and _name_match(b.name, away)
            ba = _name_match(a.name, away) and _name_match(b.name, home)
            if ab or ba:
                return event
        return None

    @staticmethod
    def _parse_bookmaker(
        bookmaker: dict[str, Any], home_team: str | None, away_team: str | None
    ) -> MatchOdds | None:
        """Extract a full 3-way h2h line from one bookmaker, or None if incomplete."""
        markets = bookmaker.get("markets") or []
        h2h = next((m for m in markets if m.get("key") == "h2h"), None)
        if h2h is None:
            return None

        prices: dict[str, float] = {}
        for outcome in h2h.get("outcomes") or []:
            name = outcome.get("name")
            price = outcome.get("price")
            if name is None or price is None:
                continue
            if _name_match(name, _DRAW_NAME):
                prices["draw"] = float(price)
            elif _name_match(name, home_team):
                prices["home"] = float(price)
            elif _name_match(name, away_team):
                prices["away"] = float(price)

        if not {"home", "draw", "away"} <= prices.keys():
            return None
        return MatchOdds(
            bookmaker=str(bookmaker.get("key") or "unknown"),
            home=prices["home"],
            draw=prices["draw"],
            away=prices["away"],
        )

    # ── OddsProvider ─────────────────────────────────────────────────────────
    async def get_match_odds(
        self, a: TeamRef, b: TeamRef, kickoff: Any = None
    ) -> MatchOdds:
        data = await self._get(
            f"/v4/sports/{_SPORT_KEY}/odds/",
            {"regions": "eu", "markets": "h2h", "oddsFormat": "decimal"},
        )
        events: list[dict[str, Any]] = data if isinstance(data, list) else []

        event = self._find_event(events, a, b)
        if event is None:
            raise NotFound(
                f"the_odds_api: no {_SPORT_KEY} event for {a.name!r} vs {b.name!r}"
            )

        home_team = event.get("home_team")
        away_team = event.get("away_team")
        bookmakers: list[dict[str, Any]] = event.get("bookmakers") or []

        # Anchor on Pinnacle; fall back to the first book with a complete h2h line.
        for bk in bookmakers:
            if bk.get("key") == _PREFERRED_BOOKMAKER:
                odds = self._parse_bookmaker(bk, home_team, away_team)
                if odds is not None:
                    return odds
        for bk in bookmakers:
            odds = self._parse_bookmaker(bk, home_team, away_team)
            if odds is not None:
                return odds

        raise NotFound(
            f"the_odds_api: no h2h odds for {a.name!r} vs {b.name!r}"
        )

    async def get_win_probabilities(
        self, a: TeamRef, b: TeamRef, kickoff: Any = None
    ) -> WinProbabilities:
        odds = await self.get_match_odds(a, b, kickoff)
        home, draw, away = devig_three_way(odds.home, odds.draw, odds.away)
        return WinProbabilities(
            home=home,
            draw=draw,
            away=away,
            source=odds.bookmaker,
            devig=True,
        )
