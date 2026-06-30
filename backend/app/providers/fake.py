"""FakeProvider — deterministic, no-network SportsDataProvider + OddsProvider.

Same inputs → same outputs (fixed datetimes, no randomness, no HTTP). Implements BOTH
Protocols from ``app.providers.base`` so graph/tool tests can run against an in-memory
checkpointer without touching a real API. Coverage is intentionally uneven (one live
match with events + lineups, one pre-match fixture with no lineups yet) so callers can
exercise the "missing/partial data" paths. (docs/plan/03-data-and-apis.md §3, spec §4)
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from app.errors import NotFound
from app.providers.base import (
    Fixture,
    FormResult,
    GroupTable,
    H2HMeeting,
    HeadToHead,
    Lineups,
    LiveMatchState,
    MatchEvent,
    MatchOdds,
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
    WinProbabilities,
    devig_three_way,
)

_PROVIDER = "fake"
_UTC = UTC

# status.short values that count as "in play" (docs §2.1)
_LIVE_STATUSES = frozenset({"1H", "HT", "2H", "ET", "BT", "P", "PEN"})


def _ref(fixture_id: str) -> ProviderRef:
    return ProviderRef(provider=_PROVIDER, id=fixture_id)


def _dt(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=_UTC)


def _date_key(value: Any) -> str | None:
    """Normalize a date / datetime / ISO-string filter down to a 'YYYY-MM-DD' key."""
    if value is None:
        return None
    if isinstance(value, str):
        return value[:10]
    if isinstance(value, datetime):  # datetime is a subclass of date — check first
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


# ── teams ────────────────────────────────────────────────────────────────────
_NETHERLANDS = Team(
    name="Netherlands", short_name="NED", country_code="NL", external_ref={_PROVIDER: "ned"}
)
_JAPAN = Team(name="Japan", short_name="JPN", country_code="JP", external_ref={_PROVIDER: "jpn"})
_SPAIN = Team(name="Spain", short_name="ESP", country_code="ES", external_ref={_PROVIDER: "esp"})
_BRAZIL = Team(name="Brazil", short_name="BRA", country_code="BR", external_ref={_PROVIDER: "bra"})

_TEAM_BY_ID = {"ned": "Netherlands", "jpn": "Japan", "esp": "Spain", "bra": "Brazil"}


def _team_name(ref: TeamRef) -> str:
    return ref.name or _TEAM_BY_ID.get(ref.id, ref.id)


def _slot(name: str, number: int, position: str) -> PlayerSlot:
    return PlayerSlot(name=name, number=number, position=position)


# ── fixtures ─────────────────────────────────────────────────────────────────
def _build_fixtures() -> list[Fixture]:
    return [
        Fixture(
            ref=_ref("1001"),
            status="1H",
            kickoff=_dt(2026, 6, 30, 19, 0),
            home=_NETHERLANDS,
            away=_JAPAN,
            score=Score(home=1, away=0),
            venue="MetLife Stadium, New York",
            round_key="Group Stage - 3",
            group="E",
            stage="Group Stage",
            elapsed=23,
        ),
        Fixture(
            ref=_ref("1002"),
            status="NS",
            kickoff=_dt(2026, 7, 1, 19, 0),
            home=_SPAIN,
            away=_BRAZIL,
            score=Score(),
            venue="AT&T Stadium, Dallas",
            round_key="Group Stage - 3",
            group="F",
            stage="Group Stage",
        ),
    ]


# ── live state (only the in-play fixture carries events) ─────────────────────
def _build_live_states() -> list[LiveMatchState]:
    return [
        LiveMatchState(
            ref=_ref("1001"),
            status="1H",
            minute=23,
            score=Score(home=1, away=0),
            events=[
                MatchEvent(
                    minute=12,
                    type="Goal",
                    detail="Normal Goal",
                    team="Netherlands",
                    player="Cody Gakpo",
                    assist="Memphis Depay",
                ),
                MatchEvent(
                    minute=18,
                    type="Card",
                    detail="Yellow Card",
                    team="Japan",
                    player="Wataru Endo",
                ),
                MatchEvent(
                    minute=21,
                    type="subst",
                    detail="Substitution 1",
                    team="Japan",
                    player="Kaoru Mitoma",
                    assist="Takefusa Kubo",
                ),
            ],
        ),
        LiveMatchState(ref=_ref("1002"), status="NS", score=Score()),
    ]


# ── lineups (published ~1h pre-kickoff; pre-match fixture has none yet) ───────
def _build_lineups() -> list[Lineups]:
    netherlands = TeamLineup(
        team="Netherlands",
        formation="4-3-3",
        starting_xi=[
            _slot("Bart Verbruggen", 1, "G"),
            _slot("Denzel Dumfries", 22, "D"),
            _slot("Virgil van Dijk", 4, "D"),
            _slot("Stefan de Vrij", 3, "D"),
            _slot("Nathan Aké", 5, "D"),
            _slot("Frenkie de Jong", 8, "M"),
            _slot("Tijjani Reijnders", 14, "M"),
            _slot("Xavi Simons", 7, "M"),
            _slot("Cody Gakpo", 11, "F"),
            _slot("Memphis Depay", 9, "F"),
            _slot("Donyell Malen", 18, "F"),
        ],
        bench=[
            _slot("Justin Bijlow", 13, "G"),
            _slot("Jurriën Timber", 2, "D"),
            _slot("Ryan Gravenberch", 6, "M"),
            _slot("Wout Weghorst", 19, "F"),
        ],
    )
    japan = TeamLineup(
        team="Japan",
        formation="4-2-3-1",
        starting_xi=[
            _slot("Zion Suzuki", 1, "G"),
            _slot("Hiroki Sakai", 2, "D"),
            _slot("Maya Yoshida", 22, "D"),
            _slot("Ko Itakura", 4, "D"),
            _slot("Yuto Nagatomo", 5, "D"),
            _slot("Wataru Endo", 6, "M"),
            _slot("Hidemasa Morita", 13, "M"),
            _slot("Junya Ito", 14, "M"),
            _slot("Takefusa Kubo", 10, "M"),
            _slot("Ritsu Doan", 8, "M"),
            _slot("Daizen Maeda", 15, "F"),
        ],
        bench=[
            _slot("Daniel Schmidt", 12, "G"),
            _slot("Shogo Taniguchi", 3, "D"),
            _slot("Kaoru Mitoma", 7, "F"),
            _slot("Ayase Ueda", 9, "F"),
        ],
    )
    return [
        Lineups(ref=_ref("1001"), home=netherlands, away=japan),
        # Pre-match fixture: lineups not published yet — graceful empty (home/away None).
        Lineups(ref=_ref("1002")),
    ]


# ── standings ────────────────────────────────────────────────────────────────
def _build_standings() -> Standings:
    return Standings(
        groups=[
            GroupTable(
                group="E",
                rows=[
                    StandingRow(
                        rank=1, team="Netherlands", played=3, win=2, draw=1, loss=0,
                        goals_for=5, goals_against=2, points=7,
                    ),
                    StandingRow(
                        rank=2, team="Japan", played=3, win=2, draw=0, loss=1,
                        goals_for=4, goals_against=3, points=6,
                    ),
                    StandingRow(
                        rank=3, team="Senegal", played=3, win=1, draw=1, loss=1,
                        goals_for=3, goals_against=3, points=4,
                    ),
                    StandingRow(
                        rank=4, team="Ecuador", played=3, win=0, draw=0, loss=3,
                        goals_for=1, goals_against=5, points=0,
                    ),
                ],
            ),
            GroupTable(
                group="F",
                rows=[
                    StandingRow(
                        rank=1, team="Brazil", played=3, win=3, draw=0, loss=0,
                        goals_for=7, goals_against=1, points=9,
                    ),
                    StandingRow(
                        rank=2, team="Spain", played=3, win=2, draw=0, loss=1,
                        goals_for=5, goals_against=3, points=6,
                    ),
                    StandingRow(
                        rank=3, team="Croatia", played=3, win=1, draw=0, loss=2,
                        goals_for=2, goals_against=4, points=3,
                    ),
                    StandingRow(
                        rank=4, team="Nigeria", played=3, win=0, draw=0, loss=3,
                        goals_for=1, goals_against=7, points=0,
                    ),
                ],
            ),
        ]
    )


# ── head-to-head (keyed by the unordered pair of team names) ─────────────────
_H2H: dict[frozenset[str], list[H2HMeeting]] = {
    frozenset({"Netherlands", "Japan"}): [
        H2HMeeting(
            date=_dt(2010, 6, 19),
            home="Netherlands",
            away="Japan",
            score=Score(home=1, away=0),
            competition="FIFA World Cup",
        ),
        H2HMeeting(
            date=_dt(2024, 9, 7),
            home="Japan",
            away="Netherlands",
            score=Score(home=2, away=2),
            competition="International Friendly",
        ),
    ],
    frozenset({"Spain", "Brazil"}): [
        H2HMeeting(
            date=_dt(2013, 6, 30),
            home="Brazil",
            away="Spain",
            score=Score(home=3, away=0),
            competition="FIFA Confederations Cup",
        ),
    ],
}


# ── recent form (most-recent first) ──────────────────────────────────────────
def _fr(opponent: str, result: str, h: int, a: int, when: datetime) -> FormResult:
    return FormResult(opponent=opponent, result=result, score=Score(home=h, away=a), date=when)  # type: ignore[arg-type]


_FORM: dict[str, list[FormResult]] = {
    "Netherlands": [
        _fr("Senegal", "D", 1, 1, _dt(2026, 6, 25)),
        _fr("Ecuador", "W", 2, 0, _dt(2026, 6, 21)),
        _fr("Mexico", "W", 2, 1, _dt(2026, 6, 14)),
        _fr("United States", "W", 3, 1, _dt(2026, 6, 10)),
        _fr("France", "L", 0, 1, _dt(2026, 6, 5)),
    ],
    "Japan": [
        _fr("Ecuador", "W", 2, 1, _dt(2026, 6, 25)),
        _fr("Senegal", "L", 0, 2, _dt(2026, 6, 21)),
        _fr("Paraguay", "W", 3, 0, _dt(2026, 6, 13)),
        _fr("Peru", "D", 1, 1, _dt(2026, 6, 9)),
        _fr("Tunisia", "W", 2, 0, _dt(2026, 6, 4)),
    ],
    "Spain": [
        _fr("Nigeria", "W", 2, 1, _dt(2026, 6, 25)),
        _fr("Croatia", "W", 3, 0, _dt(2026, 6, 21)),
        _fr("Germany", "D", 2, 2, _dt(2026, 6, 12)),
        _fr("Italy", "W", 1, 0, _dt(2026, 6, 8)),
        _fr("Switzerland", "W", 4, 1, _dt(2026, 6, 4)),
    ],
    "Brazil": [
        _fr("Croatia", "W", 2, 0, _dt(2026, 6, 25)),
        _fr("Nigeria", "W", 4, 0, _dt(2026, 6, 21)),
        _fr("Argentina", "W", 1, 0, _dt(2026, 6, 13)),
        _fr("England", "D", 1, 1, _dt(2026, 6, 9)),
        _fr("Colombia", "W", 2, 1, _dt(2026, 6, 4)),
    ],
}
_DEFAULT_FORM: list[FormResult] = [
    _fr("Opponent A", "D", 1, 1, _dt(2026, 6, 25)),
    _fr("Opponent B", "W", 2, 0, _dt(2026, 6, 21)),
    _fr("Opponent C", "L", 0, 1, _dt(2026, 6, 13)),
    _fr("Opponent D", "W", 1, 0, _dt(2026, 6, 9)),
    _fr("Opponent E", "D", 0, 0, _dt(2026, 6, 4)),
]


# ── odds (home/draw/away decimal, keyed by canonical home→away pair) ─────────
_ODDS: dict[tuple[str, str], tuple[float, float, float]] = {
    ("Netherlands", "Japan"): (1.97, 3.6, 3.6),  # worked example, docs §5
    ("Spain", "Brazil"): (2.6, 3.3, 2.7),
}
_DEFAULT_ODDS: tuple[float, float, float] = (2.5, 3.3, 2.8)


def _lookup_odds(home_name: str, away_name: str) -> tuple[float, float, float]:
    if (home_name, away_name) in _ODDS:
        return _ODDS[(home_name, away_name)]
    if (away_name, home_name) in _ODDS:  # stored the other way round → swap home/away
        h, d, a = _ODDS[(away_name, home_name)]
        return a, d, h
    return _DEFAULT_ODDS


class FakeProvider:
    """Deterministic in-memory ``SportsDataProvider`` + ``OddsProvider`` for tests/CI.

    The ``api_key`` / ``base_url`` args exist only so the factory can wire this the same
    way as the real HTTP clients; they are ignored (there is no network).
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self._fixtures: dict[str, Fixture] = {f.ref.id: f for f in _build_fixtures()}
        self._live: dict[str, LiveMatchState] = {s.ref.id: s for s in _build_live_states()}
        self._lineups: dict[str, Lineups] = {lu.ref.id: lu for lu in _build_lineups()}

    # ── SportsDataProvider ───────────────────────────────────────────────────
    async def list_fixtures(
        self, t: TournamentRef, *, date: Any = None, live: bool = False
    ) -> list[Fixture]:
        key = _date_key(date)
        out: list[Fixture] = []
        for f in self._fixtures.values():
            if live and f.status not in _LIVE_STATUSES:
                continue
            if key is not None:
                ko = f.kickoff.date().isoformat() if f.kickoff else None
                if ko != key:
                    continue
            out.append(f)
        return out

    async def get_fixture(self, ref: ProviderRef) -> Fixture:
        f = self._fixtures.get(ref.id)
        if f is None:
            raise NotFound(f"fake: no fixture with id {ref.id!r}")
        return f

    async def get_live_state(self, ref: ProviderRef) -> LiveMatchState:
        state = self._live.get(ref.id)
        if state is not None:
            return state
        if ref.id in self._fixtures:  # known fixture, no live feed → not-started shell
            return LiveMatchState(ref=_ref(ref.id), status="NS")
        raise NotFound(f"fake: no fixture with id {ref.id!r}")

    async def get_lineups(self, ref: ProviderRef) -> Lineups:
        lineups = self._lineups.get(ref.id)
        if lineups is not None:
            return lineups
        if ref.id in self._fixtures:  # known fixture, lineups not published yet
            return Lineups(ref=_ref(ref.id))
        raise NotFound(f"fake: no fixture with id {ref.id!r}")

    async def get_standings(self, t: TournamentRef) -> Standings:
        return _build_standings()

    async def get_head_to_head(self, a: TeamRef, b: TeamRef) -> HeadToHead:
        name_a, name_b = _team_name(a), _team_name(b)
        meetings = _H2H.get(frozenset({name_a, name_b}), [])
        return HeadToHead(team_a=name_a, team_b=name_b, meetings=list(meetings))

    async def get_team_form(self, team: TeamRef, n: int = 5) -> TeamForm:
        name = _team_name(team)
        results = _FORM.get(name, _DEFAULT_FORM)[: max(n, 0)]
        wdl = "".join(r.result for r in results if r.result is not None)
        return TeamForm(team=name, last_n=list(results), wdl=wdl)

    # ── OddsProvider ─────────────────────────────────────────────────────────
    async def get_match_odds(self, a: TeamRef, b: TeamRef, kickoff: Any = None) -> MatchOdds:
        home, draw, away = _lookup_odds(_team_name(a), _team_name(b))
        return MatchOdds(bookmaker="pinnacle", home=home, draw=draw, away=away)

    async def get_win_probabilities(
        self, a: TeamRef, b: TeamRef, kickoff: Any = None
    ) -> WinProbabilities:
        odds = await self.get_match_odds(a, b, kickoff)
        p_home, p_draw, p_away = devig_three_way(odds.home, odds.draw, odds.away)
        return WinProbabilities(
            home=round(p_home, 4),
            draw=round(p_draw, 4),
            away=round(p_away, 4),
            source=odds.bookmaker,
            devig=True,
        )
