"""FastAPI app: routers, CORS, OAuth session middleware, RFC-9457 problem+json handlers."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.api import auth, brackets, briefings, chat, health, leagues, tournaments
from app.config import get_settings
from app.errors import AuthError, Conflict, NotFound, ProviderError, RateLimitError
from app.lifespan import lifespan
from app.schemas.common import ProblemDetail

logging.basicConfig(level=logging.INFO)
settings = get_settings()

app = FastAPI(title="Pitch IQ API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionMiddleware, secret_key=settings.JWT_SECRET, same_site="lax")

for module in (health, auth, chat, tournaments, brackets, briefings, leagues):
    app.include_router(module.router)


def _problem(status: int, title: str, detail: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content=ProblemDetail(title=title, status=status, detail=detail).model_dump(),
    )


@app.exception_handler(AuthError)
async def _auth(request: Request, exc: AuthError):
    return _problem(401, "authentication_failed", str(exc))


@app.exception_handler(NotFound)
async def _notfound(request: Request, exc: NotFound):
    return _problem(404, "not_found", str(exc))


@app.exception_handler(Conflict)
async def _conflict(request: Request, exc: Conflict):
    return _problem(409, "conflict", str(exc))


@app.exception_handler(RateLimitError)
async def _ratelimit(request: Request, exc: RateLimitError):
    return _problem(429, "provider_rate_limited", str(exc))


@app.exception_handler(ProviderError)
async def _provider(request: Request, exc: ProviderError):
    return _problem(502, "upstream_provider_error", str(exc))


@app.exception_handler(RequestValidationError)
async def _validation(request: Request, exc: RequestValidationError):
    return _problem(422, "validation_error", str(exc.errors()))
