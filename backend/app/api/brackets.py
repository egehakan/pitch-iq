from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Bracket, BracketPick, Tournament
from app.deps import get_current_user, get_db, get_state
from app.errors import Conflict, NotFound
from app.graph.state import BracketChange
from app.schemas.bracket import (
    BracketCreateIn,
    BracketOut,
    ConfirmIn,
    InterruptInfo,
    InterruptOut,
    PerPickScore,
    PickOut,
    PicksIn,
    ScoreOut,
)
from app.services.companion import build_context, make_bracket_writer

router = APIRouter(tags=["brackets"])


def _bracket_out(b: Bracket) -> BracketOut:
    return BracketOut(
        id=b.id,
        tournament_id=b.tournament_id,
        name=b.name,
        status=b.status,
        total_score=b.total_score,
        picks=[
            PickOut(
                id=p.id, fixture_id=p.fixture_id, round_key=p.round_key, pick_type=p.pick_type,
                predicted_winner_team_id=p.predicted_winner_team_id,
                predicted_home_score=p.predicted_home_score,
                predicted_away_score=p.predicted_away_score,
                predicted_team_id=p.predicted_team_id,
                points_awarded=p.points_awarded, is_correct=p.is_correct,
            )
            for p in b.picks
        ],
    )


async def _load_bracket(db: AsyncSession, bracket_id: UUID, user_id: UUID) -> Bracket:
    b = (
        await db.execute(
            select(Bracket).where(Bracket.id == bracket_id).options(selectinload(Bracket.picks))
        )
    ).scalar_one_or_none()
    if b is None or b.user_id != user_id:
        raise NotFound("bracket not found")
    return b


@router.post("/api/brackets", response_model=BracketOut, status_code=201)
async def create_bracket(
    body: BracketCreateIn, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> BracketOut:
    existing = (
        await db.execute(
            select(Bracket).where(
                Bracket.user_id == user.id,
                Bracket.tournament_id == body.tournament_id,
                Bracket.name == body.name,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise Conflict("bracket with this name already exists")
    b = Bracket(user_id=user.id, tournament_id=body.tournament_id, name=body.name)
    db.add(b)
    await db.commit()
    b = await _load_bracket(db, b.id, user.id)
    return _bracket_out(b)


@router.get("/api/brackets", response_model=list[BracketOut])
async def my_brackets(
    tournament_id: UUID, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[BracketOut]:
    rows = (
        await db.execute(
            select(Bracket)
            .where(Bracket.user_id == user.id, Bracket.tournament_id == tournament_id)
            .options(selectinload(Bracket.picks))
            .order_by(Bracket.created_at)
        )
    ).scalars().all()
    return [_bracket_out(b) for b in rows]


@router.get("/api/brackets/{bracket_id}", response_model=BracketOut)
async def get_bracket(
    bracket_id: UUID, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> BracketOut:
    return _bracket_out(await _load_bracket(db, bracket_id, user.id))


@router.patch("/api/brackets/{bracket_id}/picks", response_model=BracketOut)
async def edit_picks(
    bracket_id: UUID, body: PicksIn, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> BracketOut:
    b = await _load_bracket(db, bracket_id, user.id)
    if b.status in ("locked", "scored"):
        raise Conflict("bracket is locked")
    existing = {(p.round_key, str(p.fixture_id)): p for p in b.picks}
    for pick in body.picks:
        key = (pick.round_key, str(pick.fixture_id))
        target = existing.get(key)
        if target is None:
            target = BracketPick(bracket_id=b.id, round_key=pick.round_key)
            db.add(target)
            b.picks.append(target)
        target.fixture_id = pick.fixture_id
        target.pick_type = pick.pick_type
        target.predicted_winner_team_id = pick.predicted_winner_team_id
        target.predicted_home_score = pick.predicted_home_score
        target.predicted_away_score = pick.predicted_away_score
        target.predicted_team_id = pick.predicted_team_id
    await db.commit()
    b = await _load_bracket(db, bracket_id, user.id)
    return _bracket_out(b)


def _thread(bracket_id: UUID) -> str:
    return f"bracket-submit:{bracket_id}"


@router.post("/api/brackets/{bracket_id}/submit")
async def submit_bracket(
    bracket_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    state: Any = Depends(get_state),
):
    b = await _load_bracket(db, bracket_id, user.id)
    if b.status == "locked":
        return _bracket_out(b)
    tournament = await db.get(Tournament, b.tournament_id)
    ctx = build_context(
        state.providers,
        tournament,
        bracket_writer=make_bracket_writer(state.sessionmaker, b.id),
    )
    change = BracketChange(
        bracket_id=str(b.id),
        action="submit",
        summary=(
            f"Submit and lock bracket “{b.name}” with {len(b.picks)} pick(s)? "
            "Once locked it cannot be edited."
        ),
        diff=[f"{p.round_key}" for p in b.picks][:12] + ["lock bracket"],
    )
    cfg = {"configurable": {"thread_id": _thread(b.id)}}
    result = await state.bracket_graph.ainvoke(
        {"messages": [], "user_id": str(user.id), "tournament_id": str(b.tournament_id),
         "pending_change": change},
        config=cfg, context=ctx, durability="sync",
    )
    if "__interrupt__" in result:
        intr = result["__interrupt__"][0]
        return InterruptOut(interrupt=InterruptInfo(id=str(getattr(intr, "id", "0")), summary=str(intr.value)))
    await db.refresh(b, attribute_names=["status", "submitted_at", "total_score"])
    return _bracket_out(b)


@router.post("/api/brackets/{bracket_id}/submit/confirm", response_model=BracketOut)
async def confirm_submit(
    bracket_id: UUID,
    body: ConfirmIn,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    state: Any = Depends(get_state),
) -> BracketOut:
    b = await _load_bracket(db, bracket_id, user.id)
    tournament = await db.get(Tournament, b.tournament_id)
    ctx = build_context(
        state.providers,
        tournament,
        bracket_writer=make_bracket_writer(state.sessionmaker, b.id),
    )
    cfg = {"configurable": {"thread_id": _thread(b.id)}}
    await state.bracket_graph.ainvoke(
        Command(resume=body.approved), config=cfg, context=ctx, durability="sync"
    )
    await db.refresh(b, attribute_names=["status", "submitted_at", "total_score"])
    return _bracket_out(b)


@router.get("/api/brackets/{bracket_id}/score", response_model=ScoreOut)
async def bracket_score(
    bracket_id: UUID, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ScoreOut:
    b = await _load_bracket(db, bracket_id, user.id)
    return ScoreOut(
        bracket_id=b.id,
        total_score=b.total_score,
        per_pick=[
            PerPickScore(
                pick_id=p.id, round_key=p.round_key,
                points_awarded=p.points_awarded, is_correct=p.is_correct,
            )
            for p in b.picks
        ],
    )
