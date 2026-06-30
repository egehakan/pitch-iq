"""Typed domain exceptions → mapped to RFC-9457 problem+json in app/main.py."""
from __future__ import annotations


class PitchIQError(Exception):
    """Base for all app domain errors."""


class AuthError(PitchIQError):
    """Authentication / authorization failure → 401."""


class NotFound(PitchIQError):
    """Requested resource does not exist → 404."""


class Conflict(PitchIQError):
    """State conflict (e.g. duplicate) → 409."""


class ProviderError(PitchIQError):
    """Upstream data provider failed after failover → 502."""


class RateLimitError(ProviderError):
    """Provider rate limit hit → 429."""
