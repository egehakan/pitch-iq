from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

BriefingType = Literal["pre_match", "post_match", "daily"]


class BriefingOut(BaseModel):
    id: UUID
    fixture_id: UUID
    type: str
    status: str
    content: str | None = None
    content_format: str = "markdown"
    model: str | None = None
    generated_at: datetime | None = None


class JobOut(BaseModel):
    job_id: str
