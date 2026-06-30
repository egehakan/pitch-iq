"""Provider abstraction: strict Pydantic DTOs + SportsDataProvider / OddsProvider Protocols.

Tools and graph nodes depend ONLY on these Protocols + models, never on a concrete
client. Swapping API-Football for football-data.org (or FakeProvider in tests) is a
config change in app/providers/__init__.py with zero graph edits. (canonical-spec §4)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── refs ────────────────────────────────────────────────────────────────────
class ProviderRef(_Strict):
    provider: str
    id: str


class TeamRef(_Strict):
    provider: str
    id: str
    name: str | None = None


class TournamentRef(_Strict):
    provider: str
    league: str
    season: str


# ── core entities ───────────────────────────────────────────────────────────
class Team(_Strict):
    name: str
    short_name: str | None = None
    country_code: str | None = None
    crest_url: str | None = None
    external_ref: dict[str, Any] = Field(default_factory=dict)


class Score(_Strict):
    home: int | None = None
    away: int | None = None


class Fixture(_Strict):
    ref: ProviderRef
    status: str = "NS"          # provider short status (NS/1H/HT/2H/ET/P/FT/AET/PEN ...)
    kickoff: datetime | None = None
    home: Team | None = None
    away: Team | None = None
    home_placeholder: str | None = None
    away_placeholder: str | None = None
    score: Score = Field(default_factory=Score)
    score_et: Score | None = None
    pens: Score | None = None
    venue: str | None = None
    round_key: str | None = None
    group: str | None = None
    stage: str | None = None
    elapsed: int | None = None
    winner: Literal["home", "away", "draw"] | None = None


class MatchEvent(_Strict):
    minute: int | None = None
    extra: int | None = None
    type: str = ""              # Goal / Card / subst / Var ...
    detail: str | None = None
    team: str | None = None
    player: str | None = None
    assist: str | None = None


class LiveMatchState(_Strict):
    ref: ProviderRef
    status: str = "NS"
    minute: int | None = None
    extra: int | None = None
    score: Score = Field(default_factory=Score)
    events: list[MatchEvent] = Field(default_factory=list)


class PlayerSlot(_Strict):
    name: str
    number: int | None = None
    position: str | None = None


class TeamLineup(_Strict):
    team: str | None = None
    formation: str | None = None
    starting_xi: list[PlayerSlot] = Field(default_factory=list)
    bench: list[PlayerSlot] = Field(default_factory=list)


class Lineups(_Strict):
    ref: ProviderRef
    home: TeamLineup | None = None
    away: TeamLineup | None = None


class StandingRow(_Strict):
    rank: int | None = None
    team: str
    played: int = 0
    win: int = 0
    draw: int = 0
    loss: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0


class GroupTable(_Strict):
    group: str
    rows: list[StandingRow] = Field(default_factory=list)


class Standings(_Strict):
    groups: list[GroupTable] = Field(default_factory=list)


class H2HMeeting(_Strict):
    date: datetime | None = None
    home: str | None = None
    away: str | None = None
    score: Score = Field(default_factory=Score)
    competition: str | None = None


class HeadToHead(_Strict):
    team_a: str | None = None
    team_b: str | None = None
    meetings: list[H2HMeeting] = Field(default_factory=list)


class FormResult(_Strict):
    opponent: str | None = None
    result: Literal["W", "D", "L"] | None = None
    score: Score = Field(default_factory=Score)
    date: datetime | None = None


class TeamForm(_Strict):
    team: str | None = None
    last_n: list[FormResult] = Field(default_factory=list)
    wdl: str = ""               # e.g. "WWDLW"


class MatchOdds(_Strict):
    bookmaker: str
    home: float
    draw: float
    away: float


class WinProbabilities(_Strict):
    home: float = Field(ge=0.0, le=1.0)
    draw: float = Field(ge=0.0, le=1.0)
    away: float = Field(ge=0.0, le=1.0)
    source: str = "unknown"
    devig: bool = True


class DataFragment(_Strict):
    """Fan-in wrapper for the parallel `gathered` channel (briefing/prediction subgraphs)."""

    kind: str                  # "fixture"|"lineups"|"standings"|"odds"|"h2h"|"form"
    payload: dict[str, Any]


# ── Protocols (tools depend only on these) ──────────────────────────────────
@runtime_checkable
class SportsDataProvider(Protocol):
    async def list_fixtures(
        self, t: TournamentRef, *, date: Any = None, live: bool = False
    ) -> list[Fixture]: ...
    async def get_fixture(self, ref: ProviderRef) -> Fixture: ...
    async def get_live_state(self, ref: ProviderRef) -> LiveMatchState: ...
    async def get_lineups(self, ref: ProviderRef) -> Lineups: ...
    async def get_standings(self, t: TournamentRef) -> Standings: ...
    async def get_head_to_head(self, a: TeamRef, b: TeamRef) -> HeadToHead: ...
    async def get_team_form(self, team: TeamRef, n: int = 5) -> TeamForm: ...


@runtime_checkable
class OddsProvider(Protocol):
    async def get_match_odds(self, a: TeamRef, b: TeamRef, kickoff: Any = None) -> MatchOdds: ...
    async def get_win_probabilities(
        self, a: TeamRef, b: TeamRef, kickoff: Any = None
    ) -> WinProbabilities: ...


def devig_three_way(home: float, draw: float, away: float) -> tuple[float, float, float]:
    """Proportional de-vig: p_i = (1/d_i) / Σ(1/d_j). (canonical-spec §4.2/§5)"""
    inv_h, inv_d, inv_a = 1.0 / home, 1.0 / draw, 1.0 / away
    s = inv_h + inv_d + inv_a
    return inv_h / s, inv_d / s, inv_a / s
