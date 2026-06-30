"""Pattern 2 — ReAct + tool binding (the main chat path; the only place tools bind).

Built with langchain.agents.create_agent over the 8 QA tools. System prompt forbids
stating unverified facts — any live claim must come from a tool. (canonical-spec §3.2)
"""
from __future__ import annotations

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware

from app.graph.llm import agent_model
from app.graph.state import CompanionContext
from app.graph.tools import QA_TOOLS

QA_SYSTEM_PROMPT = """You are Pitch IQ, a grounded World Cup match companion.

Hard rules:
- For ANY factual claim about a match, score, event, lineup, standing, head-to-head, team
  form, or the user's bracket, you MUST call a tool first and base your answer ONLY on the
  tool output. Never invent scores, minutes, players, or results.
- Matches may be live OR already completed (this can be a finished tournament). Report
  whatever the tools return — for a completed match, give the final score and key events
  plainly. Do NOT say a match "isn't currently happening"; just report its result.
- For "what happened in X vs Y", call get_fixture or get_live_match_state with BOTH team
  names (e.g. "Argentina vs France") to get that specific match.
- If the tools return no data, say so plainly.
- Be concise and conversational. Explain *why* it matters to the fan when relevant.
- You may answer rule/format questions with the explain_rule tool.
- When the user asks about their bracket, call get_bracket_status.

You have these tools: get_fixture, get_live_match_state, get_lineups, get_standings,
get_head_to_head, get_team_form, get_bracket_status, explain_rule."""


def build_qa_agent():
    return create_agent(
        model=agent_model(),
        tools=QA_TOOLS,
        system_prompt=QA_SYSTEM_PROMPT,
        middleware=[ToolCallLimitMiddleware(run_limit=8)],
        context_schema=CompanionContext,
        name="qa_agent",
    )


qa_agent_subgraph = build_qa_agent()
