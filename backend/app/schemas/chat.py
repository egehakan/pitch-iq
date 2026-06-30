from __future__ import annotations

from pydantic import BaseModel


class ChatIn(BaseModel):
    message: str
    thread_id: str | None = None
    tournament_id: str | None = None
