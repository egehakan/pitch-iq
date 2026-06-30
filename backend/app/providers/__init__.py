"""Provider factory — selects + wires concrete impls from settings.

A second tournament is a new tournaments row + provider id mapping; the engine never
branches on "is this the World Cup". (canonical-spec §4.1)
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.providers.base import OddsProvider, SportsDataProvider


@dataclass
class Providers:
    sports: SportsDataProvider
    odds: OddsProvider


def build_providers(s: Settings) -> Providers:
    # deterministic offline stack for tests / when keys are absent
    if s.USE_FAKE_PROVIDERS or not s.API_FOOTBALL_KEY:
        from app.providers.fake import FakeProvider

        fake = FakeProvider()
        return Providers(sports=fake, odds=fake)

    from app.providers.api_football import ApiFootballProvider
    from app.providers.caching import CachingProvider
    from app.providers.fake import FakeProvider
    from app.providers.football_data import FootballDataProvider
    from app.providers.the_odds_api import TheOddsApiProvider

    af = ApiFootballProvider(s.API_FOOTBALL_KEY) if s.API_FOOTBALL_KEY else None
    fd = FootballDataProvider(s.FOOTBALL_DATA_TOKEN) if s.FOOTBALL_DATA_TOKEN else None

    # WC2026 fixtures live in football-data.org, not API-Football → football-data is primary.
    if s.SPORTS_PRIMARY == "football-data" and fd is not None:
        primary, fallback, rate = fd, af, 10  # football-data free tier: 10 req/min
    else:
        primary, fallback, rate = (af or fd), (fd if af else None), 300

    sports: SportsDataProvider = CachingProvider(
        primary, fallback, live_ttl_seconds=max(s.LIVE_POLL_SECONDS, 60), rate_per_min=rate
    )
    odds: OddsProvider = (
        TheOddsApiProvider(s.THE_ODDS_API_KEY) if s.THE_ODDS_API_KEY else FakeProvider()
    )
    return Providers(sports=sports, odds=odds)
