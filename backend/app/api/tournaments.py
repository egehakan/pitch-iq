from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from app.db.models import Fixture, Team, Tournament
from app.deps import get_current_user, get_db, get_state
from app.errors import NotFound
from app.providers.base import ProviderRef, TournamentRef
from app.schemas.tournament import (
    FixtureOut,
    GroupTableOut,
    ScoreOut,
    StandingRowOut,
    StandingsOut,
    TeamOut,
    TournamentOut,
)

router = APIRouter(tags=["tournaments"])


def _team_out(t: Team | None) -> TeamOut | None:
    if t is None:
        return None
    return TeamOut(
        id=t.id, name=t.name, short_name=t.short_name, country_code=t.country_code, crest_url=t.crest_url
    )


def _fixture_out(fx: Fixture) -> FixtureOut:
    return FixtureOut(
        id=fx.id,
        stage=fx.stage,
        round_key=fx.round_key,
        group_label=fx.group_label,
        home=_team_out(fx.home_team),
        away=_team_out(fx.away_team),
        home_placeholder=fx.home_placeholder,
        away_placeholder=fx.away_placeholder,
        kickoff_at=fx.kickoff_at,
        status=fx.status,
        score=ScoreOut(home=fx.home_score, away=fx.away_score),
        venue=fx.venue,
    )


async def _load_tournament(db: AsyncSession, slug: str) -> Tournament:
    t = (await db.execute(select(Tournament).where(Tournament.slug == slug))).scalar_one_or_none()
    if t is None:
        raise NotFound(f"tournament {slug} not found")
    return t


def _tref(t: Tournament) -> TournamentRef:
    cfg = t.format_config or {}
    return TournamentRef(
        provider=str(cfg.get("provider", "api-football")),
        league=str(cfg.get("league", "1")),
        season=str(cfg.get("season", "2026")),
    )


@router.get("/api/tournaments/{slug}", response_model=TournamentOut)
async def get_tournament(slug: str, db: AsyncSession = Depends(get_db)) -> TournamentOut:
    t = await _load_tournament(db, slug)
    return TournamentOut(
        id=t.id, slug=t.slug, name=t.name, status=t.status,
        start_date=t.start_date, end_date=t.end_date,
        format_config=t.format_config or {}, scoring_config=t.scoring_config or {},
    )


@router.get("/api/tournaments/{slug}/fixtures", response_model=list[FixtureOut])
async def list_fixtures(
    slug: str, date: date | None = None, db: AsyncSession = Depends(get_db)
) -> list[FixtureOut]:
    from sqlalchemy.orm import selectinload

    t = await _load_tournament(db, slug)
    q = (
        select(Fixture)
        .where(Fixture.tournament_id == t.id)
        .options(selectinload(Fixture.home_team), selectinload(Fixture.away_team))
        .order_by(Fixture.kickoff_at)
    )
    rows = (await db.execute(q)).scalars().all()
    return [_fixture_out(fx) for fx in rows]


@router.get("/api/tournaments/{slug}/standings", response_model=StandingsOut)
async def standings(
    slug: str, db: AsyncSession = Depends(get_db), state: Any = Depends(get_state)
) -> StandingsOut:
    t = await _load_tournament(db, slug)
    try:
        st = await state.providers.sports.get_standings(_tref(t))
    except Exception:
        return StandingsOut(groups=[])
    return StandingsOut(
        groups=[
            GroupTableOut(
                group=g.group,
                rows=[
                    StandingRowOut(
                        rank=r.rank, team=r.team, played=r.played, win=r.win, draw=r.draw,
                        loss=r.loss, goals_for=r.goals_for, goals_against=r.goals_against, points=r.points,
                    )
                    for r in g.rows
                ],
            )
            for g in st.groups
        ]
    )


@router.get("/api/fixtures/{fixture_id}", response_model=FixtureOut)
async def get_fixture(fixture_id: UUID, db: AsyncSession = Depends(get_db)) -> FixtureOut:
    from sqlalchemy.orm import selectinload

    fx = (
        await db.execute(
            select(Fixture)
            .where(Fixture.id == fixture_id)
            .options(selectinload(Fixture.home_team), selectinload(Fixture.away_team))
        )
    ).scalar_one_or_none()
    if fx is None:
        raise NotFound("fixture not found")
    return _fixture_out(fx)


@router.get("/api/fixtures/{fixture_id}/live")
async def fixture_live(
    fixture_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    state: Any = Depends(get_state),
):
    fx = (await db.execute(select(Fixture).where(Fixture.id == fixture_id))).scalar_one_or_none()
    if fx is None:
        raise NotFound("fixture not found")
    ext = fx.external_ref or {}
    ref = ProviderRef(provider=str(ext.get("provider", "api-football")), id=str(ext.get("id", "0")))
    poll = max(2, min(state.settings.LIVE_POLL_SECONDS, 5))

    async def gen():
        seen = 0
        # bounded loop so a demo connection ends cleanly
        for _ in range(600):
            try:
                live = await state.providers.sports.get_live_state(ref)
            except Exception:
                live = None
            if live is not None:
                yield ServerSentEvent(
                    event="score",
                    data=json.dumps(
                        {"status": live.status, "minute": live.minute,
                         "home": live.score.home, "away": live.score.away}
                    ),
                )
                for e in live.events[seen:]:
                    yield ServerSentEvent(
                        event="match_event",
                        data=json.dumps(
                            {"minute": e.minute, "extra": e.extra, "type": e.type,
                             "detail": e.detail, "team": e.team, "player": e.player}
                        ),
                    )
                seen = len(live.events)
            await asyncio.sleep(poll)

    return EventSourceResponse(gen())
