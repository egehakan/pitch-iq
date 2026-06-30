"""API-Football (v3) concrete `SportsDataProvider`.

Primary live/fixture/standings source for Pitch IQ. Talks to
``https://v3.football.api-sports.io`` with header ``x-apisports-key`` and parses
the documented ``response`` arrays into the strict Pydantic DTOs from
``app.providers.base``. See docs/plan/03-data-and-apis.md §2.1.

WC2026 tournament identity = ``league=1, season=2026`` (carried on TournamentRef).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

import httpx

from app.errors import AuthError, NotFound, ProviderError, RateLimitError
from app.providers.base import (
    Fixture,
    FormResult,
    GroupTable,
    H2HMeeting,
    HeadToHead,
    Lineups,
    LiveMatchState,
    MatchEvent,
    PlayerSlot,
    ProviderRef,
    Score,
    StandingRow,
    Standings,
    Team,
    TeamForm,
    TeamLineup,
    TeamRef,
    TournamentRef,
)

PROVIDER = "api_football"
DEFAULT_BASE_URL = "https://v3.football.api-sports.io"
DEFAULT_TIMEOUT = 15.0

# status.short values that mean the match is finished (canonical-spec / doc §2.1).
_FINISHED_STATUSES = frozenset({"FT", "AET", "PEN"})


class ApiFootballProvider:
    """Concrete `SportsDataProvider` backed by API-Football v3."""

    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"x-apisports-key": api_key},
            timeout=httpx.Timeout(DEFAULT_TIMEOUT),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # ── HTTP plumbing ────────────────────────────────────────────────────────
    async def _request(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """GET ``path`` and return the API-Football ``response`` array (possibly empty)."""
        try:
            resp = await self._client.get(path, params=params)
        except httpx.HTTPError as exc:  # network / timeout / transport
            raise ProviderError(f"{PROVIDER} request to {path} failed: {exc}") from exc

        _raise_for_status(resp, path)

        try:
            data = resp.json()
        except ValueError as exc:
            raise ProviderError(f"{PROVIDER} returned non-JSON body for {path}") from exc

        _check_body_errors(data, path)

        response = data.get("response")
        return response if isinstance(response, list) else []

    # ── SportsDataProvider methods ───────────────────────────────────────────
    async def list_fixtures(
        self, t: TournamentRef, *, date: Any = None, live: bool = False
    ) -> list[Fixture]:
        if live:
            raw = await self._request("/fixtures", {"live": "all"})
            raw = [item for item in raw if _matches_league(item, t.league)]
        else:
            params: dict[str, Any] = {"league": t.league, "season": t.season}
            if date is not None:
                params["date"] = _format_date(date)
            raw = await self._request("/fixtures", params)
        return [_parse_fixture(item) for item in raw]

    async def get_fixture(self, ref: ProviderRef) -> Fixture:
        raw = await self._request("/fixtures", {"id": ref.id})
        if not raw:
            raise NotFound(f"{PROVIDER} fixture {ref.id} not found")
        return _parse_fixture(raw[0])

    async def get_live_state(self, ref: ProviderRef) -> LiveMatchState:
        fixtures = await self._request("/fixtures", {"id": ref.id})
        if not fixtures:
            raise NotFound(f"{PROVIDER} fixture {ref.id} not found")

        item = fixtures[0]
        fixture_obj = _as_dict(item.get("fixture"))
        status_obj = _as_dict(fixture_obj.get("status"))
        goals = _as_dict(item.get("goals"))

        events_raw = await self._request("/fixtures/events", {"fixture": ref.id})

        return LiveMatchState(
            ref=ProviderRef(provider=PROVIDER, id=str(ref.id)),
            status=status_obj.get("short") or "NS",
            minute=status_obj.get("elapsed"),
            extra=status_obj.get("extra"),
            score=_score(goals),
            events=[_parse_event(event) for event in events_raw],
        )

    async def get_lineups(self, ref: ProviderRef) -> Lineups:
        raw = await self._request("/fixtures/lineups", {"fixture": ref.id})
        home = _parse_team_lineup(raw[0]) if len(raw) > 0 else None
        away = _parse_team_lineup(raw[1]) if len(raw) > 1 else None
        return Lineups(ref=ProviderRef(provider=PROVIDER, id=str(ref.id)), home=home, away=away)

    async def get_standings(self, t: TournamentRef) -> Standings:
        raw = await self._request("/standings", {"league": t.league, "season": t.season})
        groups: list[GroupTable] = []
        for item in raw:
            league_obj = _as_dict(item.get("league"))
            tables = league_obj.get("standings") or []
            for table in tables:
                if not table:
                    continue
                first = _as_dict(table[0])
                group_name = first.get("group") or ""
                rows = [_parse_standing_row(row) for row in table]
                groups.append(GroupTable(group=group_name, rows=rows))
        return Standings(groups=groups)

    async def get_head_to_head(self, a: TeamRef, b: TeamRef) -> HeadToHead:
        raw = await self._request("/fixtures/headtohead", {"h2h": f"{a.id}-{b.id}"})
        return HeadToHead(
            team_a=a.name,
            team_b=b.name,
            meetings=[_parse_h2h_meeting(item) for item in raw],
        )

    async def get_team_form(self, team: TeamRef, n: int = 5) -> TeamForm:
        raw = await self._request("/fixtures", {"team": team.id, "last": n})
        results: list[FormResult] = []
        for item in raw:
            result = _parse_form_result(item, team.id)
            if result is not None:
                results.append(result)
        wdl = "".join(r.result for r in results if r.result)
        return TeamForm(team=team.name, last_n=results, wdl=wdl)


# ── error mapping ────────────────────────────────────────────────────────────
def _raise_for_status(resp: httpx.Response, path: str) -> None:
    code = resp.status_code
    if code < 400:
        return
    if code == 429:
        raise RateLimitError(f"{PROVIDER} rate limit hit for {path}")
    if code in (401, 403):
        raise AuthError(f"{PROVIDER} auth failed ({code}) for {path}")
    if code == 404:
        raise NotFound(f"{PROVIDER} resource not found for {path}")
    raise ProviderError(f"{PROVIDER} returned HTTP {code} for {path}")


def _check_body_errors(data: Any, path: str) -> None:
    """API-Football can return HTTP 200 with an ``errors`` object; map the known ones."""
    if not isinstance(data, dict):
        return
    errors = data.get("errors")
    if not errors:
        return
    if isinstance(errors, dict):
        keys = {str(k).lower() for k in errors}
        if keys & {"token", "key", "access"}:
            raise AuthError(f"{PROVIDER} auth error for {path}: {errors}")
        if keys & {"requests", "ratelimit", "rate_limit"}:
            raise RateLimitError(f"{PROVIDER} rate limit for {path}: {errors}")
    # Unknown / partial-coverage errors: degrade gracefully (caller sees empty data).


# ── parsing helpers ──────────────────────────────────────────────────────────
def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _format_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _score(obj: Any) -> Score:
    data = _as_dict(obj)
    return Score(home=data.get("home"), away=data.get("away"))


def _optional_score(obj: Any) -> Score | None:
    data = _as_dict(obj)
    home, away = data.get("home"), data.get("away")
    if home is None and away is None:
        return None
    return Score(home=home, away=away)


def _matches_league(item: dict[str, Any], league: str) -> bool:
    league_id = _as_dict(item.get("league")).get("id")
    return league_id is None or str(league_id) == str(league)


def _parse_team(obj: Any) -> Team | None:
    data = _as_dict(obj)
    name = data.get("name")
    if name is None:
        return None
    external_ref: dict[str, Any] = {}
    if data.get("id") is not None:
        external_ref[PROVIDER] = str(data["id"])
    return Team(name=name, crest_url=data.get("logo"), external_ref=external_ref)


def _winner(home_w: Any, away_w: Any, status: str) -> Literal["home", "away", "draw"] | None:
    if home_w is True:
        return "home"
    if away_w is True:
        return "away"
    if status in _FINISHED_STATUSES:
        return "draw"
    return None


def _extract_group(round_key: str | None) -> str | None:
    """Derive a group token from API-Football's ``round`` (e.g. 'Group A - 1' -> 'A')."""
    if not round_key:
        return None
    text = str(round_key)
    if not text.lower().startswith("group"):
        return None
    rest = text[len("group"):].replace("-", " ").split()
    return rest[0] if rest else None


def _parse_fixture(item: dict[str, Any]) -> Fixture:
    fixture_obj = _as_dict(item.get("fixture"))
    status_obj = _as_dict(fixture_obj.get("status"))
    venue_obj = _as_dict(fixture_obj.get("venue"))
    league_obj = _as_dict(item.get("league"))
    teams = _as_dict(item.get("teams"))
    home_obj = _as_dict(teams.get("home"))
    away_obj = _as_dict(teams.get("away"))
    score_obj = _as_dict(item.get("score"))
    round_key = league_obj.get("round")
    status_short = status_obj.get("short") or "NS"

    return Fixture(
        ref=ProviderRef(provider=PROVIDER, id=str(fixture_obj.get("id"))),
        status=status_short,
        kickoff=_parse_dt(fixture_obj.get("date")),
        home=_parse_team(home_obj),
        away=_parse_team(away_obj),
        score=_score(item.get("goals")),
        score_et=_optional_score(score_obj.get("extratime")),
        pens=_optional_score(score_obj.get("penalty")),
        venue=venue_obj.get("name"),
        round_key=round_key,
        group=_extract_group(round_key),
        elapsed=status_obj.get("elapsed"),
        winner=_winner(home_obj.get("winner"), away_obj.get("winner"), status_short),
    )


def _parse_event(event: dict[str, Any]) -> MatchEvent:
    time_obj = _as_dict(event.get("time"))
    return MatchEvent(
        minute=time_obj.get("elapsed"),
        extra=time_obj.get("extra"),
        type=event.get("type") or "",
        detail=event.get("detail"),
        team=_as_dict(event.get("team")).get("name"),
        player=_as_dict(event.get("player")).get("name"),
        assist=_as_dict(event.get("assist")).get("name"),
    )


def _parse_lineup_players(raw_list: Any) -> list[PlayerSlot]:
    slots: list[PlayerSlot] = []
    for entry in raw_list or []:
        player = _as_dict(_as_dict(entry).get("player"))
        name = player.get("name")
        if name is None:
            continue
        slots.append(
            PlayerSlot(name=name, number=player.get("number"), position=player.get("pos"))
        )
    return slots


def _parse_team_lineup(entry: dict[str, Any]) -> TeamLineup:
    return TeamLineup(
        team=_as_dict(entry.get("team")).get("name"),
        formation=entry.get("formation"),
        starting_xi=_parse_lineup_players(entry.get("startXI")),
        bench=_parse_lineup_players(entry.get("substitutes")),
    )


def _parse_standing_row(row: dict[str, Any]) -> StandingRow:
    all_stats = _as_dict(row.get("all"))
    goals = _as_dict(all_stats.get("goals"))
    return StandingRow(
        rank=row.get("rank"),
        team=_as_dict(row.get("team")).get("name") or "",
        played=all_stats.get("played") or 0,
        win=all_stats.get("win") or 0,
        draw=all_stats.get("draw") or 0,
        loss=all_stats.get("lose") or 0,
        goals_for=goals.get("for") or 0,
        goals_against=goals.get("against") or 0,
        points=row.get("points") or 0,
    )


def _parse_h2h_meeting(item: dict[str, Any]) -> H2HMeeting:
    fixture_obj = _as_dict(item.get("fixture"))
    teams = _as_dict(item.get("teams"))
    return H2HMeeting(
        date=_parse_dt(fixture_obj.get("date")),
        home=_as_dict(teams.get("home")).get("name"),
        away=_as_dict(teams.get("away")).get("name"),
        score=_score(item.get("goals")),
        competition=_as_dict(item.get("league")).get("name"),
    )


def _parse_form_result(item: dict[str, Any], team_id: str) -> FormResult | None:
    teams = _as_dict(item.get("teams"))
    home_obj = _as_dict(teams.get("home"))
    away_obj = _as_dict(teams.get("away"))
    goals = _as_dict(item.get("goals"))
    home_goals, away_goals = goals.get("home"), goals.get("away")
    if home_goals is None or away_goals is None:
        return None  # not yet played / no score recorded

    wanted = str(team_id)
    if str(home_obj.get("id")) == wanted:
        opponent, ours, theirs = away_obj.get("name"), home_goals, away_goals
    elif str(away_obj.get("id")) == wanted:
        opponent, ours, theirs = home_obj.get("name"), away_goals, home_goals
    else:
        return None  # team not part of this fixture

    if ours > theirs:
        result: Literal["W", "D", "L"] = "W"
    elif ours < theirs:
        result = "L"
    else:
        result = "D"

    return FormResult(
        opponent=opponent,
        result=result,
        score=Score(home=home_goals, away=away_goals),
        date=_parse_dt(_as_dict(item.get("fixture")).get("date")),
    )
