"""Pattern 7 — Human-in-the-loop (bracket submit/lock).

START → validate_change → confirm[interrupt(summary)] → (approved? apply_change : cancel) → END
apply_change is the ONLY consequential write and is idempotent: all side effects happen
AFTER interrupt(), interrupt order is deterministic, and interrupt() is never wrapped in a
bare except. Run with durability="sync". (canonical-spec §3.7)
"""
from __future__ import annotations

from langchain.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from app.graph.state import BracketChange, CompanionContext, CompanionState


async def validate_change(state: CompanionState, runtime: Runtime[CompanionContext]) -> dict:
    pending = state.get("pending_change")
    if pending is not None:
        return {"pending_change": pending}
    # derive from chat intent
    intent = state.get("intent")
    params = intent.params if intent else {}
    extras = runtime.context.extras or {}
    bracket_id = params.get("bracket_id") or extras.get("bracket_id") or ""
    action = params.get("action") or "submit"
    summary = (
        f"Submit and lock bracket {bracket_id or '(your bracket)'}? "
        "Once locked, picks for started/finished matches can no longer be edited."
    )
    change = BracketChange(
        bracket_id=str(bracket_id),
        action="submit" if action not in ("lock", "edit_picks") else action,
        summary=summary,
        diff=["lock bracket"],
    )
    return {"pending_change": change}


def confirm(state: CompanionState) -> dict:
    change = state["pending_change"]
    approved = interrupt(change.summary)  # PAUSES; persisted to checkpointer
    return {"approved": bool(approved)}


def after_confirm(state: CompanionState) -> str:
    return "apply_change" if state.get("approved") else "cancel"


async def apply_change(state: CompanionState, runtime: Runtime[CompanionContext]) -> dict:
    change = state["pending_change"]
    writer = getattr(runtime.context, "bracket_writer", None)
    result_note = "Bracket submitted and locked."
    if writer is not None:
        try:
            res = await writer(change)
            if isinstance(res, dict) and res.get("status"):
                result_note = f"Bracket '{res.get('name', '')}' is now {res.get('status')}."
        except Exception as e:
            result_note = f"Could not apply the change: {e}"
    text = f"✅ {result_note}"
    return {"final_response": text, "messages": [AIMessage(content=text)]}


async def cancel(state: CompanionState) -> dict:
    text = "No changes made — your bracket is unchanged."
    return {"final_response": text, "messages": [AIMessage(content=text)]}


def _bracket_ops_builder():
    b = StateGraph(CompanionState, context_schema=CompanionContext)
    b.add_node("validate_change", validate_change)
    b.add_node("confirm", confirm)
    b.add_node("apply_change", apply_change)
    b.add_node("cancel", cancel)
    b.add_edge(START, "validate_change")
    b.add_edge("validate_change", "confirm")
    b.add_conditional_edges("confirm", after_confirm, ["apply_change", "cancel"])
    b.add_edge("apply_change", END)
    b.add_edge("cancel", END)
    return b


def build_bracket_ops_subgraph():
    """Compiled WITHOUT a checkpointer — for use as a node in companion_graph (inherits parent)."""
    return _bracket_ops_builder().compile()


def compile_bracket_ops(checkpointer=None):
    """Standalone compiled bracket_ops WITH a checkpointer — for the brackets submit/confirm API."""
    return _bracket_ops_builder().compile(checkpointer=checkpointer)


bracket_ops_subgraph = build_bracket_ops_subgraph()
