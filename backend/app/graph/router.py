"""Pattern 1 — conditional routing.

A single cheap structured-output classifier (MODEL_ROUTER) picks the specialist.
Low confidence → CHITCHAT (asks a clarifying question). (canonical-spec §3.1)
"""
from __future__ import annotations

from langchain.messages import HumanMessage, SystemMessage

from app.graph.llm import router_model
from app.graph.state import CompanionState, Route, RouterDecision

CONFIDENCE_FLOOR = 0.6

_ROUTE_TO_NODE = {
    Route.MATCH_QA: "qa_agent",
    Route.RULES_QA: "qa_agent",
    Route.BRACKET_QA: "qa_agent",
    Route.PREDICTION: "prediction",
    Route.BRIEFING: "briefing",
    Route.BRACKET_OPS: "bracket_ops",
    Route.CHITCHAT: "chitchat",
}

ROUTER_SYSTEM = """You are the intent router for "Pitch IQ", a World Cup companion app.
Classify the user's latest message into exactly one route:

- match_qa: questions about live/finished matches, scores, events, lineups, standings, "what's happening", "why N minutes added", "was that offside in the X game".
- rules_qa: questions about the laws of the game or tournament format (offside, VAR, extra time, penalties, how teams advance).
- bracket_qa: questions ABOUT the user's existing bracket/picks/score ("how is my bracket doing", "what does this result do to my bracket").
- prediction: asking who will win / a scoreline prediction / odds for a specific upcoming match.
- briefing: asking for a pre-match briefing / preview / storyline for a specific fixture.
- bracket_ops: an INSTRUCTION to change/submit/lock the bracket ("submit my bracket", "lock it in", "pick Brazil to win the final").
- chitchat: greetings, small talk, thanks, or anything unclear.

Return route, a confidence in [0,1], optional params (e.g. team, fixture_id, team_a, team_b), and a short rationale.
If you are unsure, use chitchat with low confidence."""


async def router(state: CompanionState) -> dict:
    msgs = state["messages"]
    last_human = ""
    for m in reversed(msgs):
        content = getattr(m, "content", None)
        role = getattr(m, "type", getattr(m, "role", ""))
        if content and role in ("human", "user"):
            last_human = content if isinstance(content, str) else str(content)
            break
    if not last_human and msgs:
        last_human = str(getattr(msgs[-1], "content", ""))

    model = router_model().with_structured_output(RouterDecision, method="function_calling")
    decision: RouterDecision = await model.ainvoke(
        [SystemMessage(content=ROUTER_SYSTEM), HumanMessage(content=last_human or "hello")]
    )
    return {"intent": decision, "route": decision.route}


def pick_route(state: CompanionState) -> str:
    decision = state.get("intent")
    if decision is None or decision.confidence < CONFIDENCE_FLOOR:
        return "chitchat"
    return _ROUTE_TO_NODE[decision.route]
