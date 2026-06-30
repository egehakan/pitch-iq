"""football-data.org v4 client — fallback `SportsDataProvider` (cold backup / reconciliation).

Backs up fixtures / results / standings / H2H / form for the FIFA World Cup (competition
code ``WC``) when the primary `ApiFootballProvider` is rate-limited or down. The free tier
serves *delayed* scores and exposes no lineups/events (Deep Data is a paid add-on), so:

* ``get_lineups`` returns empty teams unless the paid lineup block is present.
* ``get_live_state`` is *derived* from the match status / minute / score, not a push feed.

Attribution required by ToS: "Football data provided by the Football-Data.org API".
Depends only on `app.providers.base` DTOs + Protocols (doc 03 §2.2 / §3, canonical-spec §4).
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
    SportsDataProvider,
    StandingRow,
    Standings,
    Team,
    TeamForm,
    TeamLineup,
    TeamRef,
    TournamentRef,
)


class FootballDataProvider(SportsDataProvider):
    """football-data.org v4 fallback. ``FootballDataProvider(token)``; header ``X-Auth-Token``."""

    PROVIDER = "football-data"
    COMPETITION = "WC"  # FIFA World Cup competition code (doc 03 §2.2)

    def __init__(
        self, token: str, *, base_url: str = "https://api.football-data.org/v4"
    ) -> None:
        self._token = token
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-Auth-Token": token},
            timeout=httpx.Timeout(15.0),
        )

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # ── HTTP plumbing ────────────────────────────────────────────────────────
    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        try:
            resp = await self._client.get(path, params=clean)
        except httpx.HTTPError as exc:  # connect/read/timeout/etc.
            raise ProviderError(f"football-data request failed: {exc}") from exc
        self._raise_for_status(resp)
        try:
            data = resp.json()
        except ValueError as exc:
            raise ProviderError("football-data returned a non-JSON response") from exc
        if not isinstance(data, dict):
            raise ProviderError("football-data returned an unexpected payload shape")
        return data

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        code = resp.status_code
        if code == 429:
            raise RateLimitError("football-data rate limit exceeded (429)")
        if code in (401, 403):
            raise AuthError(f"football-data auth failed ({code})")
        if code == 404:
            raise NotFound("football-data resource not found (404)")
        if code >= 400:
            raise ProviderError(f"football-data HTTP error {code}")

    async def _match(self, match_id: str) -> dict[str, Any]:
        data = await self._get(f"/matches/{match_id}")
        # v4 returns the match at the document root; tolerate a wrapped variant too.
        inner = data.get("match")
        return inner if isinstance(inner, dict) else data

    # ── mapping helpers ──────────────────────────────────────────────────────
    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _fmt_date(value: Any) -> str:
        if isinstance(value, date):  # datetime is a subclass of date
            return value.isoformat()[:10]
        return str(value)[:10]

    @staticmethod
    def _score(node: Any) -> Score:
        node = node or {}
        return Score(home=node.get("home"), away=node.get("away"))

    @staticmethod
    def _winner(score: dict[str, Any]) -> Literal["home", "away", "draw"] | None:
        w = (score or {}).get("winner")
        if w == "HOME_TEAM":
            return "home"
        if w == "AWAY_TEAM":
            return "away"
        if w == "DRAW":
            return "draw"
        return None

    @classmethod
    def _short_status(cls, m: dict[str, Any]) -> str:
        """Map football-data status enum → API-Football-style short code."""
        status = m.get("status")
        if status in ("SCHEDULED", "TIMED"):
            return "NS"
        if status == "IN_PLAY":
            minute = m.get("minute")
            return "2H" if isinstance(minute, int) and minute > 45 else "1H"
        if status == "PAUSED":
            return "HT"
        if status == "FINISHED":
            duration = (m.get("score") or {}).get("duration")
            if duration == "PENALTY_SHOOTOUT":
                return "PEN"
            if duration == "EXTRA_TIME":
                return "AET"
            return "FT"
        if status == "SUSPENDED":
            return "SUSP"
        if status == "POSTPONED":
            return "PST"
        if status == "CANCELLED":
            return "CANC"
        if status == "AWARDED":
            return "AWD"
        return "NS"

    @staticmethod
    def _team(node: Any) -> Team | None:
        if not node:
            return None
        name = node.get("name")
        if not name:  # TBD knockout slot → no concrete team yet
            return None
        ext: dict[str, Any] = {}
        if node.get("id") is not None:
            ext["football-data"] = str(node["id"])
        if node.get("tla"):
            ext["tla"] = node["tla"]
        return Team(
            name=name,
            short_name=node.get("shortName") or node.get("tla"),
            country_code=node.get("tla"),
            crest_url=node.get("crest"),
            external_ref=ext,
        )

    @staticmethod
    def _slot(p: dict[str, Any]) -> PlayerSlot:
        return PlayerSlot(
            name=p.get("name") or "",
            number=p.get("shirtNumber"),
            position=p.get("position"),
        )

    def _lineup(self, node: dict[str, Any] | None) -> TeamLineup | None:
        if not node:
            return None
        lineup = node.get("lineup") or []
        bench = node.get("bench") or []
        formation = node.get("formation")
        if not lineup and not bench and not formation:
            return None  # free tier: lineup/bench unavailable → empty
        return TeamLineup(
            team=node.get("name"),
            formation=formation,
            starting_xi=[self._slot(p) for p in lineup],
            bench=[self._slot(p) for p in bench],
        )

    def _events(self, m: dict[str, Any]) -> list[MatchEvent]:
        """Best-effort event feed (populated only on the paid Deep Data add-on)."""
        events: list[MatchEvent] = []
        for g in m.get("goals") or []:
            events.append(
                MatchEvent(
                    minute=g.get("minute"),
                    extra=g.get("injuryTime"),
                    type="Goal",
                    detail=g.get("type"),
                    team=(g.get("team") or {}).get("name"),
                    player=(g.get("scorer") or {}).get("name"),
                    assist=(g.get("assist") or {}).get("name"),
                )
            )
        for b in m.get("bookings") or []:
            events.append(
                MatchEvent(
                    minute=b.get("minute"),
                    type="Card",
                    detail=b.get("card"),
                    team=(b.get("team") or {}).get("name"),
                    player=(b.get("player") or {}).get("name"),
                )
            )
        for s in m.get("substitutions") or []:
            events.append(
                MatchEvent(
                    minute=s.get("minute"),
                    type="subst",
                    team=(s.get("team") or {}).get("name"),
                    player=(s.get("playerIn") or {}).get("name"),
                    assist=(s.get("playerOut") or {}).get("name"),
                )
            )
        events.sort(key=lambda e: (e.minute or 0, e.extra or 0))
        return events

    def _fixture(self, m: dict[str, Any]) -> Fixture:
        score_obj = m.get("score") or {}
        et = score_obj.get("extraTime")
        pen = score_obj.get("penalties")
        matchday = m.get("matchday")
        round_key = str(matchday) if matchday is not None else m.get("stage")
        return Fixture(
            ref=ProviderRef(provider=self.PROVIDER, id=str(m.get("id"))),
            status=self._short_status(m),
            kickoff=self._parse_dt(m.get("utcDate")),
            home=self._team(m.get("homeTeam")),
            away=self._team(m.get("awayTeam")),
            score=self._score(score_obj.get("fullTime")),
            score_et=self._score(et) if et else None,
            pens=self._score(pen) if pen else None,
            venue=m.get("venue"),
            round_key=round_key,
            group=m.get("group"),
            stage=m.get("stage"),
            elapsed=m.get("minute"),
            winner=self._winner(score_obj),
        )

    # ── SportsDataProvider Protocol ──────────────────────────────────────────
    async def list_fixtures(
        self, t: TournamentRef, *, date: Any = None, live: bool = False
    ) -> list[Fixture]:
        params: dict[str, Any] = {}
        if live:
            params["status"] = "IN_PLAY,PAUSED"
        if date is not None:
            day = self._fmt_date(date)
            params["dateFrom"] = day
            params["dateTo"] = day
        data = await self._get(f"/competitions/{self.COMPETITION}/matches", params=params)
        return [self._fixture(m) for m in data.get("matches", [])]

    async def get_fixture(self, ref: ProviderRef) -> Fixture:
        return self._fixture(await self._match(ref.id))

    async def get_live_state(self, ref: ProviderRef) -> LiveMatchState:
        m = await self._match(ref.id)
        score_obj = m.get("score") or {}
        return LiveMatchState(
            ref=ProviderRef(provider=self.PROVIDER, id=str(ref.id)),
            status=self._short_status(m),
            minute=m.get("minute"),
            extra=m.get("injuryTime"),
            score=self._score(score_obj.get("fullTime")),
            events=self._events(m),
        )

    async def get_lineups(self, ref: ProviderRef) -> Lineups:
        m = await self._match(ref.id)
        return Lineups(
            ref=ProviderRef(provider=self.PROVIDER, id=str(ref.id)),
            home=self._lineup(m.get("homeTeam")),
            away=self._lineup(m.get("awayTeam")),
        )

    async def get_standings(self, t: TournamentRef) -> Standings:
        data = await self._get(f"/competitions/{self.COMPETITION}/standings")
        groups: list[GroupTable] = []
        for s in data.get("standings", []):
            # TOTAL tables only — skip HOME/AWAY duplicates.
            if s.get("type") and s.get("type") != "TOTAL":
                continue
            group_name = s.get("group") or s.get("stage") or "GROUP"
            rows: list[StandingRow] = []
            for r in s.get("table", []):
                team = r.get("team") or {}
                rows.append(
                    StandingRow(
                        rank=r.get("position"),
                        team=team.get("name") or "",
                        played=r.get("playedGames") or 0,
                        win=r.get("won") or 0,
                        draw=r.get("draw") or 0,
                        loss=r.get("lost") or 0,
                        goals_for=r.get("goalsFor") or 0,
                        goals_against=r.get("goalsAgainst") or 0,
                        points=r.get("points") or 0,
                    )
                )
            groups.append(GroupTable(group=group_name, rows=rows))
        return Standings(groups=groups)

    async def get_head_to_head(self, a: TeamRef, b: TeamRef) -> HeadToHead:
        # football-data exposes H2H only per match-id; with two team refs we reconcile
        # meetings from the competition's finished matches (within-WC meeting at most).
        data = await self._get(
            f"/competitions/{self.COMPETITION}/matches", params={"status": "FINISHED"}
        )
        pair = {str(a.id), str(b.id)}
        meetings: list[H2HMeeting] = []
        for m in data.get("matches", []):
            home = m.get("homeTeam") or {}
            away = m.get("awayTeam") or {}
            if {str(home.get("id")), str(away.get("id"))} != pair:
                continue
            meetings.append(
                H2HMeeting(
                    date=self._parse_dt(m.get("utcDate")),
                    home=home.get("name"),
                    away=away.get("name"),
                    score=self._score((m.get("score") or {}).get("fullTime")),
                    competition="FIFA World Cup",
                )
            )
        meetings.sort(key=lambda mt: mt.date.timestamp() if mt.date else 0.0, reverse=True)
        return HeadToHead(team_a=a.name, team_b=b.name, meetings=meetings)

    async def get_team_form(self, team: TeamRef, n: int = 5) -> TeamForm:
        data = await self._get(
            f"/competitions/{self.COMPETITION}/matches", params={"status": "FINISHED"}
        )
        tid = str(team.id)
        entries: list[tuple[datetime | None, dict[str, Any]]] = []
        for m in data.get("matches", []):
            home = m.get("homeTeam") or {}
            away = m.get("awayTeam") or {}
            if tid not in (str(home.get("id")), str(away.get("id"))):
                continue
            entries.append((self._parse_dt(m.get("utcDate")), m))
        entries.sort(key=lambda e: e[0].timestamp() if e[0] else 0.0, reverse=True)

        last_n: list[FormResult] = []
        for when, m in entries[: max(n, 0)]:
            home = m.get("homeTeam") or {}
            away = m.get("awayTeam") or {}
            full = (m.get("score") or {}).get("fullTime") or {}
            is_home = str(home.get("id")) == tid
            if is_home:
                gf, ga, opp = full.get("home"), full.get("away"), away.get("name")
            else:
                gf, ga, opp = full.get("away"), full.get("home"), home.get("name")
            result: Literal["W", "D", "L"] | None = None
            if gf is not None and ga is not None:
                result = "W" if gf > ga else "L" if gf < ga else "D"
            last_n.append(
                FormResult(
                    opponent=opp,
                    result=result,
                    score=Score(home=gf, away=ga),
                    date=when,
                )
            )
        wdl = "".join(r.result for r in last_n if r.result)
        return TeamForm(team=team.name, last_n=last_n, wdl=wdl)
