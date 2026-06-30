from __future__ import annotations

import secrets
import string
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Bracket, League, LeagueMembership, User
from app.deps import get_current_user, get_db
from app.errors import Conflict, NotFound
from app.schemas.league import (
    JoinIn,
    LeaderboardOut,
    LeaderboardRow,
    LeagueCreateIn,
    LeagueOut,
)

router = APIRouter(tags=["leagues"])


def _invite_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


async def _member_count(db: AsyncSession, league_id: UUID) -> int:
    return (
        await db.execute(
            select(func.count()).select_from(LeagueMembership).where(LeagueMembership.league_id == league_id)
        )
    ).scalar_one()


@router.post("/api/leagues", response_model=LeagueOut, status_code=201)
async def create_league(
    body: LeagueCreateIn, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> LeagueOut:
    code = _invite_code()
    league = League(
        tournament_id=body.tournament_id,
        name=body.name,
        owner_user_id=user.id,
        invite_code=code,
        max_members=body.max_members,
        scoring_config=body.scoring_config,
    )
    db.add(league)
    await db.flush()
    db.add(LeagueMembership(league_id=league.id, user_id=user.id, role="owner"))
    await db.commit()
    await db.refresh(league)
    return LeagueOut(
        id=league.id, name=league.name, invite_code=league.invite_code,
        tournament_id=league.tournament_id, member_count=await _member_count(db, league.id),
        scoring_config=league.scoring_config,
    )


@router.post("/api/leagues/join", response_model=LeagueOut)
async def join_league(
    body: JoinIn, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> LeagueOut:
    league = (
        await db.execute(select(League).where(League.invite_code == body.invite_code))
    ).scalar_one_or_none()
    if league is None:
        raise NotFound("invalid invite code")
    bracket = await db.get(Bracket, body.bracket_id)
    if bracket is None or bracket.user_id != user.id:
        raise NotFound("bracket not found")
    existing = (
        await db.execute(
            select(LeagueMembership).where(
                LeagueMembership.league_id == league.id, LeagueMembership.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.bracket_id = body.bracket_id
    else:
        if await _member_count(db, league.id) >= league.max_members:
            raise Conflict("league is full")
        db.add(
            LeagueMembership(
                league_id=league.id, user_id=user.id, role="member", bracket_id=body.bracket_id
            )
        )
    await db.commit()
    return LeagueOut(
        id=league.id, name=league.name, invite_code=league.invite_code,
        tournament_id=league.tournament_id, member_count=await _member_count(db, league.id),
        scoring_config=league.scoring_config,
    )


@router.get("/api/leagues/{league_id}/leaderboard", response_model=LeaderboardOut)
async def leaderboard(
    league_id: UUID, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> LeaderboardOut:
    league = await db.get(League, league_id)
    if league is None:
        raise NotFound("league not found")
    rows_q = (
        select(LeagueMembership, User, Bracket)
        .join(User, User.id == LeagueMembership.user_id)
        .join(Bracket, Bracket.id == LeagueMembership.bracket_id, isouter=True)
        .where(LeagueMembership.league_id == league_id)
    )
    results = (await db.execute(rows_q)).all()
    rows = []
    for _membership, member, bracket in results:
        rows.append(
            LeaderboardRow(
                user_id=member.id,
                display_name=member.display_name,
                bracket_id=bracket.id if bracket else None,
                total_score=bracket.total_score if bracket else 0,
            )
        )
    rows.sort(key=lambda r: r.total_score, reverse=True)
    for i, r in enumerate(rows):
        r.rank = i + 1
    return LeaderboardOut(league_id=league_id, rows=rows)
