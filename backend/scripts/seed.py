"""Seed the tournament from REAL football-data.org data (FIFA World Cup 2026, code WC).

WC2026 fixtures aren't published in API-Football yet (0 results), but football-data.org
carries the live tournament — 104 matches, group stage finished, Round of 32 in progress.
This is the spec's "re-point at another provider/tournament with zero schema DDL" in action.

Run: cd backend && uv run python scripts/seed.py
Idempotent: wipes + reseeds the tournament (keeps users global).
"""
from __future__ import annotations

import asyncio

from sqlalchemy import delete, select

from app.config import get_settings
from app.db.models import Briefing, Fixture, Team, Tournament, TournamentTeam
from app.db.session import make_engine, make_sessionmaker
from app.providers.base import TournamentRef
from app.providers.football_data import FootballDataProvider

SLUG = "world-cup-2026"

# football-data round label  ->  bracket stage key
ROUND_MAP = {
    "LAST_32": "R32",
    "LAST_16": "R16",
    "QUARTER_FINALS": "QF",
    "SEMI_FINALS": "SF",
    "FINAL": "F",
    "THIRD_PLACE": "3P",
}
STAGES = [
    {"key": "R32", "name": "Round of 32", "order": 1},
    {"key": "R16", "name": "Round of 16", "order": 2},
    {"key": "QF", "name": "Quarterfinals", "order": 3},
    {"key": "SF", "name": "Semifinals", "order": 4},
    {"key": "F", "name": "Final", "order": 5},
]
FORMAT_CONFIG = {"provider": "football-data", "league": "WC", "season": "2026", "stages": STAGES}
SCORING_CONFIG = {"exact_score": 5, "correct_winner": 3, "correct_team": 2}


def _round_key(label: str | None) -> str:
    return ROUND_MAP.get(label or "", "GROUP")


async def main() -> None:
    s = get_settings()
    fd = FootballDataProvider(s.FOOTBALL_DATA_TOKEN)
    tref = TournamentRef(provider="football-data", league="WC", season="2026")
    print("Fetching real WC2026 fixtures from football-data.org…")
    fixtures = await fd.list_fixtures(tref)
    print(f"  got {len(fixtures)} fixtures")
    if not fixtures:
        raise SystemExit("No fixtures returned — aborting.")

    engine = make_engine(s)
    sm = make_sessionmaker(engine)
    async with sm() as db:
        for slug in (SLUG, "world-cup-2022"):
            old = (
                await db.execute(select(Tournament).where(Tournament.slug == slug))
            ).scalar_one_or_none()
            if old is not None:
                await db.execute(delete(Briefing).where(Briefing.tournament_id == old.id))
                await db.delete(old)
                await db.flush()

        tournament = Tournament(
            slug=SLUG,
            name="FIFA World Cup 2026",
            sport="football",
            status="active",
            format_config=FORMAT_CONFIG,
            scoring_config=SCORING_CONFIG,
        )
        db.add(tournament)
        await db.flush()

        existing = {t.name: t for t in (await db.execute(select(Team))).scalars().all()}
        teams: dict[str, Team] = {}

        def tkey(pt) -> str | None:
            if pt is None:
                return None
            ext = pt.external_ref or {}
            return str(ext.get("football-data") or ext.get("tla") or pt.name)

        def upsert(pt):
            if pt is None:
                return None
            k = tkey(pt)
            if k in teams:
                return teams[k]
            t = existing.get(pt.name)
            if t is None:
                t = Team(
                    name=pt.name, short_name=pt.short_name, country_code=pt.country_code,
                    crest_url=pt.crest_url, external_ref=pt.external_ref or {},
                )
                db.add(t)
            else:
                t.crest_url = pt.crest_url or t.crest_url
                t.country_code = pt.country_code or t.country_code
                t.external_ref = pt.external_ref or t.external_ref
            teams[k] = t
            return t

        seen: set[str] = set()
        for f in fixtures:
            for pt in (f.home, f.away):
                upsert(pt)
                if (k := tkey(pt)):
                    seen.add(k)
        await db.flush()
        for k in seen:
            db.add(TournamentTeam(tournament_id=tournament.id, team_id=teams[k].id))

        n = 0
        for f in fixtures:
            home = teams.get(tkey(f.home)) if f.home else None
            away = teams.get(tkey(f.away)) if f.away else None
            winner_id = None
            if f.winner == "home" and home:
                winner_id = home.id
            elif f.winner == "away" and away:
                winner_id = away.id
            db.add(
                Fixture(
                    tournament_id=tournament.id,
                    external_ref={"provider": f.ref.provider, "id": f.ref.id},
                    stage=_round_key(f.round_key),
                    round_key=_round_key(f.round_key),
                    group_label=f.group,
                    home_team_id=home.id if home else None,
                    away_team_id=away.id if away else None,
                    home_placeholder=None if home else (f.home_placeholder or "TBD"),
                    away_placeholder=None if away else (f.away_placeholder or "TBD"),
                    kickoff_at=f.kickoff,
                    venue=f.venue,
                    status=f.status,
                    home_score=f.score.home,
                    away_score=f.score.away,
                    winner_team_id=winner_id,
                )
            )
            n += 1
        await db.commit()
        print(f"Seeded '{tournament.name}' ({SLUG}): {len(seen)} teams, {n} fixtures.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
