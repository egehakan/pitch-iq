"""Helpers to run the companion graph from API endpoints — build the run context,
and bind DB-backed bracket reader/writer closures used by tools + bracket_ops."""
from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from app.db.models import Bracket, Team
from app.graph.state import BracketChange, CompanionContext
from app.providers import Providers
from app.providers.base import TournamentRef


def tournament_ref_from(tournament: Any) -> TournamentRef:
    cfg = tournament.format_config or {}
    return TournamentRef(
        provider=str(cfg.get("provider", "api-football")),
        league=str(cfg.get("league", "1")),
        season=str(cfg.get("season", "2026")),
    )


def make_bracket_reader(
    sessionmaker: async_sessionmaker, user_id: uuid.UUID, tournament_id: uuid.UUID
) -> Callable:
    async def _read() -> dict | None:
        async with sessionmaker() as db:
            bracket = (
                await db.execute(
                    select(Bracket)
                    .where(Bracket.user_id == user_id, Bracket.tournament_id == tournament_id)
                    .options(selectinload(Bracket.picks))
                    .order_by(Bracket.created_at)
                )
            ).scalars().first()
            if not bracket:
                return None
            team_names = dict(
                (t.id, t.name) for t in (await db.execute(select(Team))).scalars().all()
            )
            picks = [
                {
                    "round_key": p.round_key,
                    "predicted_winner": team_names.get(p.predicted_winner_team_id),
                    "predicted_team": team_names.get(p.predicted_team_id),
                    "predicted_home_score": p.predicted_home_score,
                    "predicted_away_score": p.predicted_away_score,
                    "is_correct": p.is_correct,
                }
                for p in bracket.picks
            ]
            return {
                "name": bracket.name,
                "status": bracket.status,
                "total_score": bracket.total_score,
                "picks": picks,
            }

    return _read


def make_bracket_writer(sessionmaker: async_sessionmaker, bracket_id: uuid.UUID) -> Callable:
    async def _write(change: BracketChange) -> dict:
        from datetime import datetime

        async with sessionmaker() as db:
            bracket = await db.get(Bracket, bracket_id)
            if not bracket:
                return {"status": "not_found"}
            bracket.status = "locked" if change.action in ("submit", "lock") else bracket.status
            bracket.submitted_at = datetime.now(UTC)
            await db.commit()
            return {"name": bracket.name, "status": bracket.status}

    return _write


def build_context(
    providers: Providers,
    tournament: Any,
    *,
    favorite_names: list[str] | None = None,
    bracket_reader: Callable | None = None,
    bracket_writer: Callable | None = None,
    has_bracket: bool = False,
    extra: dict | None = None,
) -> CompanionContext:
    extras: dict = {
        "tournament_ref": tournament_ref_from(tournament),
        "format_config": tournament.format_config or {},
        "has_bracket": has_bracket,
    }
    if favorite_names:
        extras["favorite_team_names"] = favorite_names
    if extra:
        extras.update(extra)
    return CompanionContext(
        sports=providers.sports,
        odds=providers.odds,
        bracket_reader=bracket_reader,
        bracket_writer=bracket_writer,
        extras=extras,
    )
