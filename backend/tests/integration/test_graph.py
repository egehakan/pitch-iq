from __future__ import annotations

import os

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.graph.state import BracketChange, Route
from app.graph.subgraphs.bracket_ops import compile_bracket_ops

HAS_OPENAI = bool(os.environ.get("OPENAI_API_KEY"))
openai_only = pytest.mark.skipif(not HAS_OPENAI, reason="needs OPENAI_API_KEY")


@pytest.mark.asyncio
async def test_bracket_ops_interrupt_resume_approve():
    """Deterministic HITL test — no LLM. submit interrupts, resume(True) applies once."""
    applied = {"count": 0, "status": None}

    async def writer(change: BracketChange) -> dict:
        applied["count"] += 1
        applied["status"] = "locked"
        return {"name": "B", "status": "locked"}

    from app.graph.state import CompanionContext
    from app.providers.fake import FakeProvider

    fp = FakeProvider()
    ctx = CompanionContext(sports=fp, odds=fp, bracket_writer=writer, extras={})
    g = compile_bracket_ops(checkpointer=InMemorySaver())
    change = BracketChange(bracket_id="b1", action="submit", summary="Lock it?")
    cfg = {"configurable": {"thread_id": "t1"}}
    out = await g.ainvoke(
        {"messages": [], "user_id": "u", "tournament_id": "t", "pending_change": change},
        config=cfg, context=ctx, durability="sync",
    )
    assert "__interrupt__" in out
    assert "Lock it?" in str(out["__interrupt__"][0].value)
    assert applied["count"] == 0  # not applied before confirm
    resumed = await g.ainvoke(Command(resume=True), config=cfg, context=ctx, durability="sync")
    assert applied["count"] == 1  # applied exactly once
    assert applied["status"] == "locked"
    assert "final_response" in resumed


@pytest.mark.asyncio
async def test_bracket_ops_interrupt_resume_reject():
    async def writer(change: BracketChange) -> dict:  # pragma: no cover
        raise AssertionError("must not write on reject")

    from app.graph.state import CompanionContext
    from app.providers.fake import FakeProvider

    fp = FakeProvider()
    ctx = CompanionContext(sports=fp, odds=fp, bracket_writer=writer, extras={})
    g = compile_bracket_ops(checkpointer=InMemorySaver())
    change = BracketChange(bracket_id="b1", action="submit", summary="Lock it?")
    cfg = {"configurable": {"thread_id": "t2"}}
    await g.ainvoke(
        {"messages": [], "user_id": "u", "tournament_id": "t", "pending_change": change},
        config=cfg, context=ctx, durability="sync",
    )
    resumed = await g.ainvoke(Command(resume=False), config=cfg, context=ctx, durability="sync")
    assert "unchanged" in resumed["final_response"].lower()


@openai_only
@pytest.mark.asyncio
async def test_routing_match_qa(graph, context):
    out = await graph.ainvoke(
        {"messages": [("user", "What's the score in the Netherlands match?")],
         "user_id": "u", "tournament_id": "t"},
        config={"configurable": {"thread_id": "r1"}}, context=context,
    )
    assert out["route"] in (Route.MATCH_QA, Route.RULES_QA, Route.BRACKET_QA)


@openai_only
@pytest.mark.asyncio
async def test_prediction_loop_terminates(graph, context):
    out = await graph.ainvoke(
        {"messages": [("user", "Predict Spain vs Brazil")],
         "user_id": "u", "tournament_id": "t"},
        config={"configurable": {"thread_id": "r2"}}, context=context,
    )
    # critic loop is hard-capped at <= 2 rounds
    assert out.get("prediction_round", 0) <= 2
    p = out["prediction"].probabilities
    assert abs((p.home + p.draw + p.away) - 1.0) < 0.05


@openai_only
@pytest.mark.asyncio
async def test_briefing_sections_deterministic_order(graph, context):
    out = await graph.ainvoke(
        {"messages": [("user", "Give me a briefing for Spain vs Brazil")],
         "user_id": "u", "tournament_id": "t"},
        config={"configurable": {"thread_id": "r3"}}, context=context,
    )
    secs = out.get("briefing_sections") or []
    orders = [s.order for s in secs]
    assert orders == sorted(orders)
    assert len(secs) >= 2
