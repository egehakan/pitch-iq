from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Briefing
from app.deps import get_current_user, get_db, get_state
from app.errors import NotFound
from app.schemas.briefing import BriefingOut, BriefingType, JobOut
from app.services.briefing_service import generate_briefing

router = APIRouter(tags=["briefings"])


def _out(row: Briefing) -> BriefingOut:
    return BriefingOut(
        id=row.id, fixture_id=row.fixture_id, type=row.type, status=row.status,
        content=row.content, content_format=row.content_format, model=row.model,
        generated_at=row.generated_at,
    )


@router.get("/api/fixtures/{fixture_id}/briefing", response_model=BriefingOut)
async def get_briefing(
    fixture_id: UUID,
    type: BriefingType = "pre_match",
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    state: Any = Depends(get_state),
) -> BriefingOut:
    row = (
        await db.execute(
            select(Briefing).where(
                Briefing.fixture_id == fixture_id,
                Briefing.type == type,
                Briefing.user_id.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is not None and row.status == "ready":
        return _out(row)
    if row is not None and row.status == "generating":
        return _out(row)
    # generate on demand (first request); cached thereafter
    row_id = await generate_briefing(
        fixture_id, sessionmaker=state.sessionmaker, providers=state.providers, btype=type
    )
    row = await db.get(Briefing, row_id)
    if row is None:
        raise NotFound("briefing not found")
    await db.refresh(row)
    return _out(row)


@router.post("/api/briefings/{fixture_id}/generate", response_model=JobOut, status_code=202)
async def generate_briefing_now(
    fixture_id: UUID, user=Depends(get_current_user), state: Any = Depends(get_state)
) -> JobOut:
    import asyncio

    asyncio.create_task(
        generate_briefing(fixture_id, sessionmaker=state.sessionmaker, providers=state.providers)
    )
    return JobOut(job_id=f"briefing:{fixture_id}")
