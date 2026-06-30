"""Auth: PyJWT HS256 sessions + pwdlib[argon2] password hashing + Authlib Google OAuth.

Google is only the identity handshake; our HS256 JWT stays the session credential.
(canonical-spec §6, backend-plan §3.2)
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from authlib.integrations.starlette_client import OAuth
from pwdlib import PasswordHash

from app.config import Settings, get_settings
from app.errors import AuthError

_pwd = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return _pwd.verify(password, hashed)
    except Exception:
        return False


def create_access_token(sub: str, *, settings: Settings | None = None) -> str:
    s = settings or get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.ACCESS_TOKEN_TTL_MIN)).timestamp()),
    }
    return jwt.encode(payload, s.JWT_SECRET, algorithm=s.JWT_ALG)


def decode_token(token: str, *, settings: Settings | None = None) -> dict:
    s = settings or get_settings()
    try:
        return jwt.decode(token, s.JWT_SECRET, algorithms=[s.JWT_ALG])
    except jwt.PyJWTError as e:  # noqa: B902
        raise AuthError(f"invalid token: {e}") from e


@lru_cache
def get_oauth() -> OAuth:
    s = get_settings()
    oauth = OAuth()
    if s.GOOGLE_CLIENT_ID and s.GOOGLE_CLIENT_SECRET:
        oauth.register(
            name="google",
            client_id=s.GOOGLE_CLIENT_ID,
            client_secret=s.GOOGLE_CLIENT_SECRET,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
    return oauth
