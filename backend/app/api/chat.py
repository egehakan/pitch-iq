"""Chat — structured agent-run stream.

Streams NDJSON events so the client can show the agent working the way an analyst shows
working: which specialist was routed to, each tool call (with status + duration), and the
answer streaming token by token.

Event shapes (one JSON object per line):
  {"type":"route","route":"match_qa","agent":"qa_agent","label":"Match analyst"}
  {"type":"tool","id":"...","name":"get_live_match_state","label":"Reading the live match","arg":"Netherlands","status":"running"}
  {"type":"tool","id":"...","status":"done"}
  {"type":"text","delta":"..."}
  {"type":"done"}
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import FavoriteTeam, Team, Tournament
from app.deps import get_current_user, get_db, get_state
from app.schemas.chat import ChatIn
from app.services.companion import build_context, make_bracket_reader

router = APIRouter(tags=["chat"])

# qa_agent's inner model node + the chitchat node are the only user-facing token sources.
TOKEN_NODES = {"model", "chitchat"}

AGENT_LABELS = {
    "qa_agent": "Match analyst",
    "prediction": "Prediction desk",
    "briefing": "Briefing writer",
    "bracket_ops": "Bracket",
    "chitchat": "Companion",
}
_ROUTE_TO_AGENT = {
    "match_qa": "qa_agent", "rules_qa": "qa_agent", "bracket_qa": "qa_agent",
    "prediction": "prediction", "briefing": "briefing",
    "bracket_ops": "bracket_ops", "chitchat": "chitchat",
}
TOOL_LABELS = {
    "get_fixture": "Looking up the match",
    "get_live_match_state": "Reading the live match",
    "get_lineups": "Pulling lineups",
    "get_standings": "Checking standings",
    "get_head_to_head": "Reviewing head-to-head",
    "get_team_form": "Checking recent form",
    "get_bracket_status": "Reading your bracket",
    "explain_rule": "Checking the rulebook",
}


def _tool_arg(data: Any) -> str:
    try:
        inp = (data or {}).get("input")
        if isinstance(inp, dict):
            vals = [str(v) for v in inp.values() if isinstance(v, str | int | float) and str(v)]
            return ", ".join(vals)[:60]
        if isinstance(inp, str):
            return inp[:60]
    except Exception:
        pass
    return ""


async def _resolve_tournament(db: AsyncSession, ident: str | None) -> Tournament | None:
    settings = get_settings()
    if ident:
        t = (await db.execute(select(Tournament).where(Tournament.slug == ident))).scalar_one_or_none()
        if t:
            return t
        try:
            t = await db.get(Tournament, uuid.UUID(ident))
            if t:
                return t
        except (ValueError, Exception):
            pass
    return (
        await db.execute(select(Tournament).where(Tournament.slug == settings.TOURNAMENT_SLUG))
    ).scalar_one_or_none()


@router.post("/api/chat")
async def chat(
    body: ChatIn,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    state: Any = Depends(get_state),
):
    tournament = await _resolve_tournament(db, body.tournament_id)
    fav_names = (
        await db.execute(
            select(Team.name).join(FavoriteTeam, FavoriteTeam.team_id == Team.id).where(
                FavoriteTeam.user_id == user.id
            )
        )
    ).scalars().all()
    reader = make_bracket_reader(state.sessionmaker, user.id, tournament.id) if tournament else None
    ctx = (
        build_context(
            state.providers, tournament, favorite_names=list(fav_names),
            bracket_reader=reader, has_bracket=reader is not None,
        )
        if tournament
        else None
    )
    thread_id = body.thread_id or f"chat:{user.id}:{uuid.uuid4()}"
    cfg = {"configurable": {"thread_id": thread_id}}
    graph_input = {
        "messages": [("user", body.message)],
        "user_id": str(user.id),
        "tournament_id": str(tournament.id) if tournament else "",
    }

    def line(obj: dict) -> str:
        return json.dumps(obj, ensure_ascii=False) + "\n"

    async def gen():
        if ctx is None:
            yield line({"type": "text", "delta": "No tournament is configured yet."})
            yield line({"type": "done"})
            return
        streamed = 0
        try:
            async for ev in state.graph.astream_events(
                graph_input, config=cfg, context=ctx, version="v2"
            ):
                etype = ev["event"]
                name = ev.get("name")
                node = ev.get("metadata", {}).get("langgraph_node")
                if etype == "on_chain_end" and name == "router":
                    decision = (ev["data"].get("output") or {}).get("intent")
                    route = getattr(getattr(decision, "route", None), "value", None) or "chitchat"
                    agent = _ROUTE_TO_AGENT.get(route, "chitchat")
                    yield line({"type": "route", "route": route, "agent": agent,
                                "label": AGENT_LABELS.get(agent, "Companion")})
                elif etype == "on_tool_start":
                    yield line({"type": "tool", "id": str(ev.get("run_id")), "name": name,
                                "label": TOOL_LABELS.get(name, name), "arg": _tool_arg(ev.get("data")),
                                "status": "running"})
                elif etype == "on_tool_end":
                    yield line({"type": "tool", "id": str(ev.get("run_id")), "name": name,
                                "status": "done"})
                elif etype == "on_chat_model_stream" and node in TOKEN_NODES:
                    chunk = ev["data"].get("chunk")
                    content = getattr(chunk, "content", "")
                    if content and isinstance(content, str):
                        streamed += len(content)
                        yield line({"type": "text", "delta": content})
        except Exception as e:  # noqa: BLE001
            yield line({"type": "error", "message": str(e)[:200]})
            yield line({"type": "done"})
            return
        # specialists that assemble (prediction/briefing/bracket_ops) don't stream tokens
        if streamed == 0:
            try:
                snap = await state.graph.aget_state(cfg)
                if getattr(snap, "interrupts", None):
                    yield line({"type": "text", "delta": str(snap.interrupts[0].value)})
                elif snap.values.get("final_response"):
                    yield line({"type": "text", "delta": snap.values["final_response"]})
            except Exception:
                pass
        yield line({"type": "done"})

    return StreamingResponse(
        gen(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
