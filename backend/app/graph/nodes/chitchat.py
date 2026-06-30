"""chitchat node — plain LLM reply for greetings/small-talk/low-confidence routes.

Streams tokens (user-facing node). Asks a clarifying question when the router was
unsure. (canonical-spec §3.1)
"""
from __future__ import annotations

from langchain.messages import SystemMessage

from app.graph.llm import chitchat_model
from app.graph.state import CompanionState

CHITCHAT_SYSTEM = """You are Pitch IQ, a friendly, knowledgeable World Cup companion.
Keep replies short and warm. If the user's request was unclear, ask one concise clarifying
question and mention what you can help with: live match Q&A, rule explanations, predictions,
pre-match briefings, and managing their bracket. Never invent match facts or scores."""


async def chitchat(state: CompanionState) -> dict:
    msgs = state["messages"]
    fav = ""
    uc = state.get("user_context")
    if uc and uc.favorite_team_names:
        fav = f" The user's favorite teams: {', '.join(uc.favorite_team_names)}."
    resp = await chitchat_model().ainvoke([SystemMessage(content=CHITCHAT_SYSTEM + fav), *msgs])
    content = resp.content if isinstance(resp.content, str) else str(resp.content)
    return {"messages": [resp], "final_response": content}
