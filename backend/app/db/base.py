"""SQLAlchemy declarative base — all app tables live in the `app` schema."""
from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

APP_SCHEMA = "app"


class Base(DeclarativeBase):
    metadata = MetaData(schema=APP_SCHEMA)
