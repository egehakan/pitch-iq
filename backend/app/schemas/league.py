from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class LeagueCreateIn(BaseModel):
    tournament_id: UUID
    name: str
    max_members: int = 50
    scoring_config: dict | None = None


class JoinIn(BaseModel):
    invite_code: str
    bracket_id: UUID


class LeagueOut(BaseModel):
    id: UUID
    name: str
    invite_code: str
    tournament_id: UUID
    member_count: int = 0
    scoring_config: dict | None = None


class LeaderboardRow(BaseModel):
    user_id: UUID
    display_name: str
    bracket_id: UUID | None = None
    total_score: int = 0
    rank: int = 0


class LeaderboardOut(BaseModel):
    league_id: UUID
    rows: list[LeaderboardRow] = []
