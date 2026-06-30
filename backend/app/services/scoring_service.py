"""Bracket scoring — settle each pick vs the fixture outcome using tournaments.scoring_config
(overridable per league). brackets.total_score is denormalized for leaderboard reads.
(canonical-spec §5)"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Bracket, BracketPick, Fixture, Tournament

DEFAULT_SCORING = {"exact_score": 5, "correct_winner": 3, "correct_team": 2}

FINISHED = {"FT", "AET", "PEN"}


def score_pick(pick: BracketPick, fixture: Fixture, cfg: dict) -> tuple[int, bool]:
    points = 0
    correct = False
    # winner pick
    if pick.predicted_winner_team_id and fixture.winner_team_id:
        if pick.predicted_winner_team_id == fixture.winner_team_id:
            points += int(cfg.get("correct_winner", 3))
            correct = True
    # team-advance pick
    if pick.predicted_team_id and fixture.winner_team_id:
        if pick.predicted_team_id == fixture.winner_team_id:
            points += int(cfg.get("correct_team", 2))
            correct = True
    # exact scoreline
    if (
        pick.predicted_home_score is not None
        and pick.predicted_away_score is not None
        and fixture.home_score is not None
        and fixture.away_score is not None
    ):
        if (
            pick.predicted_home_score == fixture.home_score
            and pick.predicted_away_score == fixture.away_score
        ):
            points += int(cfg.get("exact_score", 5))
            correct = True
    return points, correct


async def score_settled_fixtures(sessionmaker: async_sessionmaker) -> int:
    settled = 0
    async with sessionmaker() as db:
        tournaments = {t.id: (t.scoring_config or DEFAULT_SCORING) for t in (await db.execute(select(Tournament))).scalars().all()}
        finished = (
            await db.execute(select(Fixture).where(Fixture.status.in_(FINISHED)))
        ).scalars().all()
        finished_ids = [f.id for f in finished]
        fixtures_by_id = {f.id: f for f in finished}
        if not finished_ids:
            return 0
        picks = (
            await db.execute(
                select(BracketPick).where(
                    BracketPick.fixture_id.in_(finished_ids),
                    BracketPick.points_awarded.is_(None),
                )
            )
        ).scalars().all()
        affected: set[uuid.UUID] = set()
        for pick in picks:
            fixture = fixtures_by_id.get(pick.fixture_id)
            if fixture is None:
                continue
            cfg = tournaments.get(fixture.tournament_id, DEFAULT_SCORING)
            pts, correct = score_pick(pick, fixture, cfg)
            pick.points_awarded = pts
            pick.is_correct = correct
            pick.scored_at = datetime.now(UTC)
            affected.add(pick.bracket_id)
            settled += 1
        # recompute denormalized totals
        for bid in affected:
            b = (
                await db.execute(select(Bracket).where(Bracket.id == bid))
            ).scalar_one()
            total = sum(
                p.points_awarded or 0
                for p in (
                    await db.execute(select(BracketPick).where(BracketPick.bracket_id == bid))
                ).scalars().all()
            )
            b.total_score = total
            if b.status in ("submitted", "locked"):
                b.status = "scored"
        await db.commit()
    return settled
