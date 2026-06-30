"""Tool registry for the qa_agent ReAct loop (exactly 8 bound tools)."""
from __future__ import annotations

from app.graph.tools.bracket import get_bracket_status
from app.graph.tools.rules import explain_rule
from app.graph.tools.sports import (
    get_fixture,
    get_head_to_head,
    get_lineups,
    get_live_match_state,
    get_standings,
    get_team_form,
)

QA_TOOLS = [
    get_fixture,
    get_live_match_state,
    get_lineups,
    get_standings,
    get_head_to_head,
    get_team_form,
    get_bracket_status,
    explain_rule,
]

__all__ = ["QA_TOOLS"]
