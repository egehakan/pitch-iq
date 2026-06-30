from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.deps import get_state
from app.schemas.common import HealthOut

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthOut)
async def healthz(state: Any = Depends(get_state)) -> HealthOut:
    db_ok = "down"
    try:
        async with state.sessionmaker() as s:
            await s.execute(text("SELECT 1"))
        db_ok = "ok"
    except Exception:
        db_ok = "down"
    cp = "ok" if getattr(state, "checkpointer", None) is not None else "memory"
    return HealthOut(status="ok", db=db_ok, checkpointer=cp)
