"""ingest node — load cross-thread user facts from the Store into user_context.

(canonical-spec §3.6) Store namespace: ("user", user_id). Robust when no store is
attached (dev/test) — falls back to a minimal UserContext.
"""
from __future__ import annotations

from langgraph.runtime import Runtime

from app.graph.state import CompanionContext, CompanionState, UserContext


async def ingest(state: CompanionState, runtime: Runtime[CompanionContext]) -> dict:
    uid = state["user_id"]
    ctx = UserContext(user_id=uid)
    store = getattr(runtime, "store", None)
    if store is not None:
        try:
            items = await store.asearch(("user", uid))
            for item in items or []:
                val = item.value if hasattr(item, "value") else {}
                if item.key == "profile":
                    ctx.favorite_team_ids = val.get("favorite_team_ids", ctx.favorite_team_ids)
                    ctx.favorite_team_names = val.get("favorite_team_names", ctx.favorite_team_names)
                    ctx.tone = val.get("tone", ctx.tone)
                    ctx.timezone = val.get("timezone", ctx.timezone)
                    ctx.locale = val.get("locale", ctx.locale)
                elif item.key == "notes":
                    ctx.notes = val.get("notes", ctx.notes)
        except Exception:
            pass
    # run context may also carry favorites injected by the API layer
    extras = getattr(runtime.context, "extras", None) or {}
    if extras.get("favorite_team_names"):
        ctx.favorite_team_names = extras["favorite_team_names"]
    if extras.get("user_tz"):
        ctx.timezone = extras["user_tz"]
    return {"user_context": ctx}
