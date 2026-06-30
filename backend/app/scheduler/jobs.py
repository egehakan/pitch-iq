"""Scheduler jobs (canonical-spec §6 / backend-plan §6).

Jobs are module-level functions taking only serializable args; runtime deps (sessionmaker,
providers, scheduler) come from a process-global holder set at startup so persisted jobs
remain re-loadable.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.services.briefing_service import generate_briefing as _generate_briefing
from app.services.poller import poll_live as _poll_live


@dataclass
class _Runtime:
    sessionmaker: Any = None
    providers: Any = None
    settings: Any = None
    scheduler: Any = None


RUNTIME = _Runtime()


def init_jobs(*, sessionmaker, providers, settings, scheduler) -> None:
    RUNTIME.sessionmaker = sessionmaker
    RUNTIME.providers = providers
    RUNTIME.settings = settings
    RUNTIME.scheduler = scheduler


async def generate_briefing(fixture_id: str) -> None:
    if RUNTIME.sessionmaker is None:
        return
    try:
        await _generate_briefing(
            uuid.UUID(fixture_id), sessionmaker=RUNTIME.sessionmaker, providers=RUNTIME.providers
        )
    except Exception:  # noqa: BLE001
        pass


async def poll_live() -> None:
    if RUNTIME.sessionmaker is None:
        return
    try:
        await _poll_live(RUNTIME.sessionmaker, RUNTIME.providers)
    except Exception:  # noqa: BLE001
        pass


async def schedule_briefings(tournament_id: str | None = None) -> None:
    from app.db.models import Fixture

    if RUNTIME.sessionmaker is None or RUNTIME.scheduler is None:
        return
    lead = RUNTIME.settings.BRIEFING_LEAD_HOURS
    now = datetime.now(UTC)
    async with RUNTIME.sessionmaker() as db:
        q = select(Fixture).where(Fixture.status == "NS")
        if tournament_id:
            q = q.where(Fixture.tournament_id == uuid.UUID(tournament_id))
        fixtures = (await db.execute(q)).scalars().all()
    for fx in fixtures:
        if not fx.kickoff_at:
            continue
        run_date = fx.kickoff_at - timedelta(hours=lead)
        if run_date <= now:
            continue
        RUNTIME.scheduler.add_job(
            generate_briefing,
            "date",
            run_date=run_date,
            args=[str(fx.id)],
            id=f"briefing:{fx.id}",
            replace_existing=True,
        )


async def nightly_sync() -> None:
    await schedule_briefings()
