"""Application settings (pydantic-settings, reads .env)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENV: str = "dev"

    # Postgres
    DATABASE_URL: str = "postgresql+asyncpg://pitchiq:pitchiq@localhost:5433/pitchiq"
    SYNC_DATABASE_URL: str = "postgresql+psycopg://pitchiq:pitchiq@localhost:5433/pitchiq"
    CHECKPOINTER_DB_URL: str = (
        "postgresql://pitchiq:pitchiq@localhost:5433/pitchiq?options=-c%20search_path%3Dlanggraph"
    )

    # OpenAI
    OPENAI_API_KEY: str = ""
    MODEL_ROUTER: str = "gpt-4o-mini"
    MODEL_AGENT: str = "gpt-4o-mini"
    MODEL_CRITIC: str = "gpt-4o"

    # Providers
    API_FOOTBALL_KEY: str = ""
    FOOTBALL_DATA_TOKEN: str = ""
    THE_ODDS_API_KEY: str = ""

    # Auth
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALG: str = "HS256"
    ACCESS_TOKEN_TTL_MIN: int = 1440
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"

    # LangSmith
    LANGSMITH_TRACING: bool = False
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "pitch-iq"

    # Runtime
    RUN_SCHEDULER: bool = False
    CORS_ORIGINS: str = "http://localhost:3000"
    LIVE_POLL_SECONDS: int = 60
    BRIEFING_LEAD_HOURS: int = 2
    TOURNAMENT_SLUG: str = "world-cup-2026"

    # Provider toggles
    USE_FAKE_PROVIDERS: bool = False
    SPORTS_PRIMARY: str = "football-data"  # "football-data" (has WC2026) | "api-football"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
