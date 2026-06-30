"""Dependency-injection surface (canonical-spec §6 / backend-plan §3.2)."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.models import User
from app.errors import AuthError
from app.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_settings_dep() -> Settings:
    return get_settings()


def get_state(request: Request) -> Any:
    return request.app.state


async def get_db(state: Any = Depends(get_state)) -> AsyncIterator[AsyncSession]:
    async with state.sessionmaker() as session:
        yield session


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not token:
        raise AuthError("missing bearer token")
    payload = decode_token(token)
    sub = payload.get("sub")
    if not sub:
        raise AuthError("token missing subject")
    import uuid

    try:
        uid = uuid.UUID(str(sub))
    except ValueError as e:
        raise AuthError("bad subject") from e
    user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if user is None:
        raise AuthError("user not found")
    return user
