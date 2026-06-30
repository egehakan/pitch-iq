"""persist_memory node — write durable cross-thread user facts to the Store.

(canonical-spec §3.6) Namespace ("user", user_id). Persists the profile snapshot
(favorites/tone/tz) learned this turn. Robust when no store is attached.
"""
from __future__ import annotations

from langgraph.runtime import Runtime

from app.graph.state import CompanionContext, CompanionState


async def persist_memory(state: CompanionState, runtime: Runtime[CompanionContext]) -> dict:
    uid = state["user_id"]
    store = getattr(runtime, "store", None)
    uc = state.get("user_context")
    if store is not None and uc is not None:
        try:
            await store.aput(
                ("user", uid),
                "profile",
                {
                    "favorite_team_ids": uc.favorite_team_ids,
                    "favorite_team_names": uc.favorite_team_names,
                    "tone": uc.tone,
                    "timezone": uc.timezone,
                    "locale": uc.locale,
                },
            )
            if uc.notes:
                await store.aput(("user", uid), "notes", {"notes": uc.notes})
        except Exception:
            pass
    return {}
