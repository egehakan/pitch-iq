from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import FavoriteTeam, User
from app.deps import get_current_user, get_db
from app.errors import AuthError, Conflict, NotFound
from app.schemas.auth import FavTeamsIn, RegisterIn, TokenOut, UserOut
from app.security import (
    create_access_token,
    get_oauth,
    hash_password,
    verify_password,
)

router = APIRouter(tags=["auth"])


async def _favorite_ids(db: AsyncSession, user_id) -> list:
    rows = (await db.execute(select(FavoriteTeam.team_id).where(FavoriteTeam.user_id == user_id))).scalars().all()
    return list(rows)


async def _user_out(db: AsyncSession, user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=str(user.email),
        display_name=user.display_name,
        timezone=user.timezone,
        auth_provider=user.auth_provider,
        favorite_team_ids=await _favorite_ids(db, user.id),
    )


@router.post("/api/auth/register", response_model=TokenOut, status_code=201)
async def register(body: RegisterIn, db: AsyncSession = Depends(get_db)) -> TokenOut:
    existing = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if existing is not None:
        raise Conflict("email already registered")
    user = User(
        email=body.email,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        auth_provider="password",
        timezone=body.timezone,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return TokenOut(access_token=create_access_token(str(user.id)))


@router.post("/api/auth/login", response_model=TokenOut)
async def login(
    form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
) -> TokenOut:
    user = (await db.execute(select(User).where(User.email == form.username))).scalar_one_or_none()
    if user is None or not verify_password(form.password, user.password_hash):
        raise AuthError("invalid email or password")
    return TokenOut(access_token=create_access_token(str(user.id)))


@router.get("/api/auth/google/login")
async def google_login(request: Request) -> RedirectResponse:
    s = get_settings()
    oauth = get_oauth()
    if not getattr(oauth, "google", None):
        raise NotFound("Google OAuth is not configured")
    return await oauth.google.authorize_redirect(request, s.OAUTH_REDIRECT_URI)


@router.get("/api/auth/google/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    s = get_settings()
    oauth = get_oauth()
    if not getattr(oauth, "google", None):
        raise NotFound("Google OAuth is not configured")
    token = await oauth.google.authorize_access_token(request)
    info = token.get("userinfo") or {}
    sub = info.get("sub")
    email = info.get("email")
    name = info.get("name") or (email.split("@")[0] if email else "Player")
    if not sub or not email:
        raise AuthError("Google profile missing sub/email")
    user = (
        await db.execute(
            select(User).where(User.auth_provider == "google", User.auth_subject == sub)
        )
    ).scalar_one_or_none()
    if user is None:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(email=email, display_name=name, auth_provider="google", auth_subject=sub)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    jwt_token = create_access_token(str(user.id))
    # hand the session token back to the frontend
    frontend = s.CORS_ORIGINS.split(",")[0].strip() or "http://localhost:3000"
    return RedirectResponse(url=f"{frontend}/login?token={jwt_token}")


@router.get("/api/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> UserOut:
    return await _user_out(db, user)


@router.put("/api/me/favorite-teams", response_model=UserOut)
async def set_favorites(
    body: FavTeamsIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    await db.execute(delete(FavoriteTeam).where(FavoriteTeam.user_id == user.id))
    for tid in body.team_ids:
        db.add(FavoriteTeam(user_id=user.id, team_id=tid))
    await db.commit()
    return await _user_out(db, user)
