"""App-schema ORM models (canonical-spec §5). Config-driven: tournaments.format_config /
scoring_config + provider id mapping de-hardcode the engine — a 2nd tournament is a new
row, zero DDL."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_provider: Mapped[str] = mapped_column(String(20), default="password", nullable=False)
    auth_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(60), default="UTC", nullable=False)
    locale: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    favorites: Mapped[list[FavoriteTeam]] = relationship(back_populates="user", cascade="all, delete-orphan")
    brackets: Mapped[list[Bracket]] = relationship(back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("auth_provider", "auth_subject", name="uq_user_auth_subject"),)


class Tournament(Base):
    __tablename__ = "tournaments"
    id: Mapped[uuid.UUID] = _uuid_pk()
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    sport: Mapped[str] = mapped_column(String(40), default="football", nullable=False)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    format_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    scoring_config: Mapped[dict] = mapped_column(JSONB, default=dict)


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    crest_url: Mapped[str | None] = mapped_column(String(400), nullable=True)
    external_ref: Mapped[dict] = mapped_column(JSONB, default=dict)


class TournamentTeam(Base):
    __tablename__ = "tournament_teams"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tournament_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tournaments.id", ondelete="CASCADE"))
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    group_label: Mapped[str | None] = mapped_column(String(8), nullable=True)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    __table_args__ = (UniqueConstraint("tournament_id", "team_id", name="uq_tt"),)


class FavoriteTeam(Base):
    __tablename__ = "favorite_teams"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    user: Mapped[User] = relationship(back_populates="favorites")
    team: Mapped[Team] = relationship()
    __table_args__ = (UniqueConstraint("user_id", "team_id", name="uq_fav"),)


class Fixture(Base):
    __tablename__ = "fixtures"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tournament_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tournaments.id", ondelete="CASCADE"))
    external_ref: Mapped[dict] = mapped_column(JSONB, default=dict)
    stage: Mapped[str | None] = mapped_column(String(40), nullable=True)
    round_key: Mapped[str | None] = mapped_column(String(40), nullable=True)
    group_label: Mapped[str | None] = mapped_column(String(8), nullable=True)
    home_team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    away_team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    home_placeholder: Mapped[str | None] = mapped_column(String(80), nullable=True)
    away_placeholder: Mapped[str | None] = mapped_column(String(80), nullable=True)
    kickoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    venue: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="NS", nullable=False)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_score_et: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score_et: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_pens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_pens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    winner_team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    raw: Mapped[dict] = mapped_column(JSONB, default=dict)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    home_team: Mapped[Team | None] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped[Team | None] = relationship(foreign_keys=[away_team_id])


class Bracket(Base):
    __tablename__ = "brackets"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tournament_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tournaments.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120), default="My Bracket", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)  # draft|submitted|locked|scored
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="brackets")
    picks: Mapped[list[BracketPick]] = relationship(
        back_populates="bracket", cascade="all, delete-orphan"
    )
    __table_args__ = (UniqueConstraint("user_id", "tournament_id", "name", name="uq_bracket"),)


class BracketPick(Base):
    __tablename__ = "bracket_picks"
    id: Mapped[uuid.UUID] = _uuid_pk()
    bracket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brackets.id", ondelete="CASCADE"))
    fixture_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fixtures.id"), nullable=True)
    round_key: Mapped[str] = mapped_column(String(40), nullable=False)
    pick_type: Mapped[str] = mapped_column(String(30), default="winner", nullable=False)
    predicted_winner_team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    predicted_home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    predicted_away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    predicted_team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    points_awarded: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    bracket: Mapped[Bracket] = relationship(back_populates="picks")


class League(Base):
    __tablename__ = "leagues"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tournament_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tournaments.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    invite_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    visibility: Mapped[str] = mapped_column(String(20), default="private", nullable=False)
    scoring_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    max_members: Mapped[int] = mapped_column(Integer, default=50, nullable=False)

    memberships: Mapped[list[LeagueMembership]] = relationship(
        back_populates="league", cascade="all, delete-orphan"
    )


class LeagueMembership(Base):
    __tablename__ = "league_memberships"
    id: Mapped[uuid.UUID] = _uuid_pk()
    league_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20), default="member", nullable=False)
    bracket_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("brackets.id"), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    league: Mapped[League] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship()
    bracket: Mapped[Bracket | None] = relationship()
    __table_args__ = (UniqueConstraint("league_id", "user_id", name="uq_membership"),)


class Briefing(Base):
    __tablename__ = "briefings"
    id: Mapped[uuid.UUID] = _uuid_pk()
    fixture_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fixtures.id", ondelete="CASCADE"))
    tournament_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tournaments.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(20), default="pre_match", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_format: Mapped[str] = mapped_column(String(20), default="markdown", nullable=False)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    thread_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    tournament_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tournaments.id"), nullable=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
