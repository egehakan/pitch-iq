"""Rules explainer tool — grounded football + tournament-format rule explanations.

Knockout-stage specifics come from the tournament's format_config when available
(injected into the run context); generic laws of the game are a curated knowledge base.
"""
from __future__ import annotations

from langchain.tools import tool
from langgraph.runtime import get_runtime

from app.graph.state import CompanionContext

_RULES: dict[str, str] = {
    "added time": (
        "Added (stoppage) time compensates for time lost in a half — substitutions, injuries, VAR "
        "checks, goal celebrations and time-wasting. The fourth official signals a minimum; the "
        "referee may add more. It is shown as e.g. 90+4."
    ),
    "stoppage": "See 'added time': stoppage time compensates for time lost during a half (subs, injuries, VAR, celebrations).",
    "offside": (
        "A player is offside if they are nearer to the opponents' goal line than both the ball and "
        "the second-last defender at the moment a team-mate plays the ball, AND they are involved in "
        "active play. Being level is onside. You can't be offside from a throw-in, goal kick or corner."
    ),
    "var": (
        "VAR (Video Assistant Referee) reviews four match-changing decisions: goals, penalties, direct "
        "red cards, and mistaken identity. The on-field referee makes the final call, often after an "
        "on-field review."
    ),
    "penalty shootout": (
        "If a knockout match is level after extra time, it's decided by a penalty shootout: five kicks "
        "each, alternating, then sudden death if still level."
    ),
    "extra time": (
        "In the knockout stage a draw after 90 minutes goes to extra time: two 15-minute halves. If "
        "still level, a penalty shootout decides the winner."
    ),
    "knockout": (
        "Knockout matches must produce a winner: if level after 90 minutes, two 15-minute halves of "
        "extra time are played, then a penalty shootout if still tied. Single elimination — the loser "
        "is out."
    ),
    "group stage": (
        "In the group stage teams play a round-robin; 3 points for a win, 1 for a draw, 0 for a loss. "
        "Top finishers advance; ties are broken by goal difference, goals scored, then head-to-head."
    ),
    "yellow card": "A yellow card is a caution. Two yellows in one match = a red (sent off). Yellow-card accumulation across matches can trigger a suspension.",
    "red card": "A red card means the player is sent off and the team plays a man down; the player is suspended for at least the next match.",
}


@tool
async def explain_rule(question: str) -> str:
    """Explain a football law or tournament-format rule (offside, added time, VAR, extra time, penalties, group/knockout format)."""
    q = (question or "").lower()
    for key, text in _RULES.items():
        if key in q:
            return text
    # token overlap fallback
    for key, text in _RULES.items():
        if any(tok in q for tok in key.split()):
            return text
    # knockout-format from tournament config when relevant
    if any(w in q for w in ("advance", "format", "rounds", "bracket", "stage")):
        ctx = get_runtime(CompanionContext).context
        cfg = (ctx.extras or {}).get("format_config") if ctx.extras else None
        if cfg:
            return f"Tournament format: {cfg}"
        return _RULES["knockout"]
    return (
        "I can explain offside, added/stoppage time, VAR, extra time, penalty shootouts, yellow/red "
        "cards, and the group/knockout format. Which would you like?"
    )
