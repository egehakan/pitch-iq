"""Headless briefing generation — runs the briefing subgraph and upserts the briefings row.

Invoked by the scheduler ('date' job at kickoff−lead) and on-demand by the briefings API.
(canonical-spec §3.4 / backend-plan §6)
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Briefing, Fixture, Tournament
from app.graph.subgraphs.briefing import briefing_subgraph
from app.providers import Providers
from app.services.companion import build_context


async def _get_or_create_row(db, fixture: Fixture, btype: str) -> Briefing:
    row = (
        await db.execute(
            select(Briefing).where(
                Briefing.fixture_id == fixture.id,
                Briefing.type == btype,
                Briefing.user_id.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = Briefing(
            fixture_id=fixture.id,
            tournament_id=fixture.tournament_id,
            user_id=None,
            type=btype,
            status="pending",
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


async def generate_briefing(
    fixture_id: uuid.UUID,
    *,
    sessionmaker: async_sessionmaker,
    providers: Providers,
    btype: str = "pre_match",
) -> uuid.UUID:
    async with sessionmaker() as db:
        fixture = await db.get(Fixture, fixture_id)
        if fixture is None:
            raise ValueError("fixture not found")
        tournament = await db.get(Tournament, fixture.tournament_id)
        home = (await _team_name(db, fixture.home_team_id)) or fixture.home_placeholder or ""
        row = await _get_or_create_row(db, fixture, btype)
        row.status = "generating"
        await db.commit()
        row_id = row.id

    ext = fixture.external_ref or {}
    ctx = build_context(
        providers,
        tournament,
        extra={"briefing_fixture_id": str(ext.get("id", "")), "briefing_team": home},
    )
    try:
        out = await briefing_subgraph.ainvoke(
            {"messages": [], "user_id": "system", "tournament_id": str(tournament.id)},
            config={"configurable": {"thread_id": f"briefing:{fixture_id}"}},
            context=ctx,
        )
        briefing = out.get("briefing")
        markdown = (briefing.markdown if briefing else out.get("final_response")) or "_No briefing available._"
        async with sessionmaker() as db:
            row = await db.get(Briefing, row_id)
            row.status = "ready"
            row.content = markdown
            row.model = briefing.model if briefing else "briefing-subgraph"
            row.thread_id = f"briefing:{fixture_id}"
            row.generated_at = datetime.now(UTC)
            await db.commit()
    except Exception as e:  # noqa: BLE001
        async with sessionmaker() as db:
            row = await db.get(Briefing, row_id)
            row.status = "failed"
            row.error = str(e)[:500]
            await db.commit()
        raise
    return row_id


async def _team_name(db, team_id) -> str | None:
    if not team_id:
        return None
    from app.db.models import Team

    t = await db.get(Team, team_id)
    return t.name if t else None
