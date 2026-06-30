"""Live poller — refreshes the fixtures cache from the provider during live windows,
then triggers scoring on FT. Runs in the single scheduler process. (canonical-spec §4.3)"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Fixture
from app.providers import Providers
from app.providers.base import ProviderRef
from app.services.scoring_service import FINISHED, score_settled_fixtures

LIVE_STATUSES = {"1H", "HT", "2H", "ET", "BT", "P"}  # PEN = finished-via-shootout, not live


async def poll_live(sessionmaker: async_sessionmaker, providers: Providers) -> int:
    updated = 0
    finished_now = False
    async with sessionmaker() as db:
        candidates = (
            await db.execute(
                select(Fixture).where(Fixture.status.in_(LIVE_STATUSES | {"NS"}))
            )
        ).scalars().all()
        for fx in candidates:
            ext = fx.external_ref or {}
            ref = ProviderRef(provider=str(ext.get("provider", "api-football")), id=str(ext.get("id", "0")))
            try:
                live = await providers.sports.get_live_state(ref)
            except Exception:
                continue
            if live.status and live.status != "NS":
                fx.status = live.status
                if live.score.home is not None:
                    fx.home_score = live.score.home
                if live.score.away is not None:
                    fx.away_score = live.score.away
                fx.fetched_at = datetime.now(UTC)
                if live.status in FINISHED and fx.winner_team_id is None:
                    if (fx.home_score or 0) > (fx.away_score or 0):
                        fx.winner_team_id = fx.home_team_id
                    elif (fx.away_score or 0) > (fx.home_score or 0):
                        fx.winner_team_id = fx.away_team_id
                    finished_now = True
                updated += 1
        await db.commit()
    if finished_now:
        await score_settled_fixtures(sessionmaker)
    return updated
