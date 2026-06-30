from __future__ import annotations

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str
    db: str
    checkpointer: str


class ProblemDetail(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
