"""Bracket tool — read the current user's bracket status for grounded Q&A.

The API layer injects an already-bound async reader into the run context
(CompanionContext.bracket_reader) so this tool needs no ids of its own.
"""
from __future__ import annotations

from langchain.tools import tool
from langgraph.runtime import get_runtime

from app.graph.state import CompanionContext


@tool
async def get_bracket_status(_: str = "") -> str:
    """Get the current user's bracket: name, status, total score, and their picks per round."""
    ctx = get_runtime(CompanionContext).context
    reader = getattr(ctx, "bracket_reader", None)
    if reader is None:
        return "No bracket is linked to this conversation yet. Create one to get bracket-aware answers."
    try:
        data = await reader()
    except Exception as e:
        return f"Could not read your bracket: {e}"
    if not data:
        return "You don't have a bracket for this tournament yet."
    picks = data.get("picks") or []
    head = f"Bracket '{data.get('name')}' — status: {data.get('status')}, score: {data.get('total_score', 0)}."
    if not picks:
        return head + " No picks made yet."
    lines = [
        f"  {p.get('round_key', '?')}: {p.get('predicted_winner') or p.get('predicted_team') or '—'}"
        + (f" ({p.get('predicted_home_score')}-{p.get('predicted_away_score')})" if p.get('predicted_home_score') is not None else "")
        + (" ✓" if p.get('is_correct') else (" ✗" if p.get('is_correct') is False else ""))
        for p in picks
    ]
    return head + "\nPicks:\n" + "\n".join(lines)
