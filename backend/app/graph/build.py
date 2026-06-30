"""companion_graph — the top-level supervisor/router graph.

ingest → router →{ qa_agent | prediction | briefing | bracket_ops | chitchat }
       → persist_memory → END
Checkpointer + store attach ONLY at compile() (passed in by app/lifespan.py). Each
mandated pattern is a labeled subgraph/module. (canonical-spec §3)
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.graph.nodes.chitchat import chitchat
from app.graph.nodes.ingest import ingest
from app.graph.nodes.persist_memory import persist_memory
from app.graph.router import pick_route, router
from app.graph.state import CompanionContext, CompanionState
from app.graph.subgraphs.bracket_ops import bracket_ops_subgraph
from app.graph.subgraphs.briefing import briefing_subgraph
from app.graph.subgraphs.prediction import prediction_subgraph
from app.graph.subgraphs.qa_agent import qa_agent_subgraph

_SPECIALISTS = ("qa_agent", "prediction", "briefing", "bracket_ops", "chitchat")


def build_graph():
    builder = StateGraph(CompanionState, context_schema=CompanionContext)
    builder.add_node("ingest", ingest)
    builder.add_node("router", router)
    builder.add_node("qa_agent", qa_agent_subgraph)
    builder.add_node("prediction", prediction_subgraph)
    builder.add_node("briefing", briefing_subgraph)
    builder.add_node("bracket_ops", bracket_ops_subgraph)
    builder.add_node("chitchat", chitchat)
    builder.add_node("persist_memory", persist_memory)

    builder.add_edge(START, "ingest")
    builder.add_edge("ingest", "router")
    builder.add_conditional_edges("router", pick_route, list(_SPECIALISTS))
    for n in _SPECIALISTS:
        builder.add_edge(n, "persist_memory")
    builder.add_edge("persist_memory", END)
    return builder


def compile_graph(checkpointer: Any = None, store: Any = None):
    return build_graph().compile(checkpointer=checkpointer, store=store)
