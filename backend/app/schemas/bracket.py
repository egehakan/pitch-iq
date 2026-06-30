from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class BracketCreateIn(BaseModel):
    tournament_id: UUID
    name: str = "My Bracket"


class PickIn(BaseModel):
    fixture_id: UUID | None = None
    round_key: str
    pick_type: str = "winner"
    predicted_winner_team_id: UUID | None = None
    predicted_home_score: int | None = None
    predicted_away_score: int | None = None
    predicted_team_id: UUID | None = None


class PicksIn(BaseModel):
    picks: list[PickIn]


class ConfirmIn(BaseModel):
    approved: bool


class PickOut(BaseModel):
    id: UUID
    fixture_id: UUID | None = None
    round_key: str
    pick_type: str
    predicted_winner_team_id: UUID | None = None
    predicted_home_score: int | None = None
    predicted_away_score: int | None = None
    predicted_team_id: UUID | None = None
    points_awarded: int | None = None
    is_correct: bool | None = None


class BracketOut(BaseModel):
    id: UUID
    tournament_id: UUID
    name: str
    status: str
    total_score: int
    picks: list[PickOut] = []


class PerPickScore(BaseModel):
    pick_id: UUID
    round_key: str
    points_awarded: int | None = None
    is_correct: bool | None = None


class ScoreOut(BaseModel):
    bracket_id: UUID
    total_score: int
    per_pick: list[PerPickScore] = []


class InterruptInfo(BaseModel):
    id: str
    summary: str


class InterruptOut(BaseModel):
    interrupt: InterruptInfo
