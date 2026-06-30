from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    display_name: str = Field(min_length=1, max_length=120)
    timezone: str = "UTC"


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: UUID
    email: str
    display_name: str
    timezone: str
    auth_provider: str
    favorite_team_ids: list[UUID] = []


class FavTeamsIn(BaseModel):
    team_ids: list[UUID]
