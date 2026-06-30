from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TeamOut(BaseModel):
    id: UUID | None = None
    name: str
    short_name: str | None = None
    country_code: str | None = None
    crest_url: str | None = None


class ScoreOut(BaseModel):
    home: int | None = None
    away: int | None = None


class TournamentOut(BaseModel):
    id: UUID
    slug: str
    name: str
    status: str
    start_date: datetime | None = None
    end_date: datetime | None = None
    format_config: dict = {}
    scoring_config: dict = {}


class FixtureOut(BaseModel):
    id: UUID
    stage: str | None = None
    round_key: str | None = None
    group_label: str | None = None
    home: TeamOut | None = None
    away: TeamOut | None = None
    home_placeholder: str | None = None
    away_placeholder: str | None = None
    kickoff_at: datetime | None = None
    status: str = "NS"
    score: ScoreOut = ScoreOut()
    venue: str | None = None


class StandingRowOut(BaseModel):
    rank: int | None = None
    team: str
    played: int = 0
    win: int = 0
    draw: int = 0
    loss: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0


class GroupTableOut(BaseModel):
    group: str
    rows: list[StandingRowOut] = []


class StandingsOut(BaseModel):
    groups: list[GroupTableOut] = []


class MatchEventOut(BaseModel):
    id: str
    minute: int | None = None
    extra: int | None = None
    type: str
    detail: str | None = None
    team: str | None = None
    player: str | None = None
