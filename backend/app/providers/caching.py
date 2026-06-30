"""CachingProvider — decorator over a SportsDataProvider.

Adds: TTL cache (live state on a short TTL), a simple async token-bucket rate limiter,
exponential backoff on rate-limit/provider errors, and failover to a fallback provider
for non-live reads. Depends only on the SportsDataProvider Protocol. (canonical-spec §4.3)
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from app.errors import ProviderError, RateLimitError
from app.providers.base import (
    Fixture,
    HeadToHead,
    Lineups,
    LiveMatchState,
    ProviderRef,
    SportsDataProvider,
    Standings,
    TeamForm,
    TeamRef,
    TournamentRef,
)


class _TokenBucket:
    def __init__(self, rate_per_min: int) -> None:
        self.capacity = max(1, rate_per_min)
        self.tokens = float(self.capacity)
        self.refill_per_sec = self.capacity / 60.0
        self.updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.refill_per_sec)
            self.updated = now
            if self.tokens < 1.0:
                wait = (1.0 - self.tokens) / self.refill_per_sec
                await asyncio.sleep(min(wait, 5.0))
                self.tokens = 0.0
            else:
                self.tokens -= 1.0


class CachingProvider:
    def __init__(
        self,
        primary: SportsDataProvider,
        fallback: SportsDataProvider | None = None,
        *,
        ttl_seconds: int = 21600,
        live_ttl_seconds: int = 60,
        rate_per_min: int = 300,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.ttl = ttl_seconds
        self.live_ttl = live_ttl_seconds
        self.bucket = _TokenBucket(rate_per_min)
        self._cache: dict[str, tuple[float, Any]] = {}

    # ── cache helpers ────────────────────────────────────────────────────────
    def _get(self, key: str, ttl: int) -> Any | None:
        hit = self._cache.get(key)
        if hit and (time.monotonic() - hit[0]) < ttl:
            return hit[1]
        return None

    def _put(self, key: str, value: Any) -> None:
        self._cache[key] = (time.monotonic(), value)

    async def _call(self, method: str, *args, failover: bool = False, **kwargs):
        await self.bucket.acquire()
        delay = 0.5
        last_exc: Exception | None = None
        for _ in range(3):
            try:
                return await getattr(self.primary, method)(*args, **kwargs)
            except (RateLimitError, ProviderError) as e:
                last_exc = e
                await asyncio.sleep(delay)
                delay *= 2
        if failover and self.fallback is not None:
            return await getattr(self.fallback, method)(*args, **kwargs)
        raise last_exc or ProviderError(f"{method} failed")

    # ── SportsDataProvider surface ───────────────────────────────────────────
    async def list_fixtures(
        self, t: TournamentRef, *, date: Any = None, live: bool = False
    ) -> list[Fixture]:
        key = f"list_fixtures:{t.league}:{t.season}:{date}:{live}"
        ttl = self.live_ttl if live else self.ttl
        cached = self._get(key, ttl)
        if cached is not None:
            return cached
        res = await self._call("list_fixtures", t, date=date, live=live, failover=not live)
        self._put(key, res)
        return res

    async def get_fixture(self, ref: ProviderRef) -> Fixture:
        key = f"get_fixture:{ref.provider}:{ref.id}"
        cached = self._get(key, self.ttl)
        if cached is not None:
            return cached
        res = await self._call("get_fixture", ref, failover=True)
        self._put(key, res)
        return res

    async def get_live_state(self, ref: ProviderRef) -> LiveMatchState:
        key = f"get_live_state:{ref.provider}:{ref.id}"
        cached = self._get(key, self.live_ttl)
        if cached is not None:
            return cached
        res = await self._call("get_live_state", ref, failover=False)
        self._put(key, res)
        return res

    async def get_lineups(self, ref: ProviderRef) -> Lineups:
        key = f"get_lineups:{ref.provider}:{ref.id}"
        cached = self._get(key, 3600)
        if cached is not None:
            return cached
        res = await self._call("get_lineups", ref, failover=False)
        self._put(key, res)
        return res

    async def get_standings(self, t: TournamentRef) -> Standings:
        key = f"get_standings:{t.league}:{t.season}"
        cached = self._get(key, self.ttl)
        if cached is not None:
            return cached
        res = await self._call("get_standings", t, failover=True)
        self._put(key, res)
        return res

    async def get_head_to_head(self, a: TeamRef, b: TeamRef) -> HeadToHead:
        key = f"h2h:{a.id}:{b.id}:{a.name}:{b.name}"
        cached = self._get(key, self.ttl)
        if cached is not None:
            return cached
        res = await self._call("get_head_to_head", a, b, failover=True)
        self._put(key, res)
        return res

    async def get_team_form(self, team: TeamRef, n: int = 5) -> TeamForm:
        key = f"form:{team.id}:{team.name}:{n}"
        cached = self._get(key, self.ttl)
        if cached is not None:
            return cached
        res = await self._call("get_team_form", team, n, failover=True)
        self._put(key, res)
        return res
