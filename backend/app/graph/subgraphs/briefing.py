"""Patterns 3 + 4 — briefing subgraph (parallel gather + Send-API orchestrator–worker).

START → fan-out gather_{fixture,lineups,standings,odds,h2h,form} (∥, operator.add→gathered)
      → plan_briefing (defer; data-dependent section list)
      → Send("write_section", spec) per section (∥ workers)
      → assemble (defer fan-in) → END
Invoked two ways: chat route BRIEFING, and headless by the scheduler. (canonical-spec §3.4)
"""
from __future__ import annotations

from datetime import UTC, datetime

from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Send
from typing_extensions import TypedDict

from app.graph.llm import agent_model
from app.graph.state import (
    Briefing,
    BriefingPlan,
    BriefingSection,
    CompanionContext,
    CompanionState,
    SectionSpec,
)
from app.providers.base import (
    DataFragment,
    Fixture,
    ProviderRef,
    TeamRef,
    TournamentRef,
)


def _norm(s: str) -> str:
    return (s or "").strip().lower()


async def _resolve_target(state: CompanionState, runtime: Runtime[CompanionContext]) -> Fixture | None:
    extras = runtime.context.extras or {}
    sports = runtime.context.sports
    tref: TournamentRef | None = extras.get("tournament_ref")
    # headless scheduler path may pass an explicit fixture ref id
    target_id = extras.get("briefing_fixture_id")
    try:
        fixtures = await sports.list_fixtures(tref) if tref else []
    except Exception:
        fixtures = []
    if target_id:
        for fx in fixtures:
            if fx.ref.id == str(target_id):
                return fx
    intent = state.get("intent")
    params = intent.params if intent else {}
    team = params.get("team") or params.get("team_a") or extras.get("briefing_team") or ""
    if team:
        for fx in fixtures:
            names = " ".join(_norm(t.name) for t in (fx.home, fx.away) if t)
            if _norm(team) in names:
                return fx
    # default: next upcoming or first
    upcoming = [f for f in fixtures if f.status in ("NS", "TBD")]
    if upcoming:
        return upcoming[0]
    return fixtures[0] if fixtures else None


def _teams(fx: Fixture | None) -> tuple[str, str]:
    if not fx:
        return "Home", "Away"
    h = fx.home.name if fx.home else (fx.home_placeholder or "Home")
    a = fx.away.name if fx.away else (fx.away_placeholder or "Away")
    return h, a


# ── parallel gather_* nodes ───────────────────────────────────────────────────
async def gather_fixture(state: CompanionState, runtime: Runtime[CompanionContext]) -> dict:
    fx = await _resolve_target(state, runtime)
    if not fx:
        return {"gathered": []}
    return {"gathered": [DataFragment(kind="fixture", payload=fx.model_dump(mode="json"))]}


async def gather_lineups(state: CompanionState, runtime: Runtime[CompanionContext]) -> dict:
    fx = await _resolve_target(state, runtime)
    if not fx:
        return {"gathered": []}
    try:
        lu = await runtime.context.sports.get_lineups(fx.ref)
        return {"gathered": [DataFragment(kind="lineups", payload=lu.model_dump(mode="json"))]}
    except Exception:
        return {"gathered": []}


async def gather_standings(state: CompanionState, runtime: Runtime[CompanionContext]) -> dict:
    tref = (runtime.context.extras or {}).get("tournament_ref")
    if not tref:
        return {"gathered": []}
    try:
        st = await runtime.context.sports.get_standings(tref)
        return {"gathered": [DataFragment(kind="standings", payload=st.model_dump(mode="json"))]}
    except Exception:
        return {"gathered": []}


async def gather_odds(state: CompanionState, runtime: Runtime[CompanionContext]) -> dict:
    fx = await _resolve_target(state, runtime)
    if not fx:
        return {"gathered": []}
    h, a = _teams(fx)
    try:
        probs = await runtime.context.odds.get_win_probabilities(
            TeamRef(provider="odds", id="0", name=h), TeamRef(provider="odds", id="0", name=a)
        )
        return {"gathered": [DataFragment(kind="odds", payload=probs.model_dump(mode="json"))]}
    except Exception:
        return {"gathered": []}


async def gather_h2h(state: CompanionState, runtime: Runtime[CompanionContext]) -> dict:
    fx = await _resolve_target(state, runtime)
    if not fx:
        return {"gathered": []}
    h, a = _teams(fx)
    try:
        h2h = await runtime.context.sports.get_head_to_head(
            TeamRef(provider="api-football", id="0", name=h),
            TeamRef(provider="api-football", id="0", name=a),
        )
        return {"gathered": [DataFragment(kind="h2h", payload=h2h.model_dump(mode="json"))]}
    except Exception:
        return {"gathered": []}


async def gather_form(state: CompanionState, runtime: Runtime[CompanionContext]) -> dict:
    fx = await _resolve_target(state, runtime)
    if not fx:
        return {"gathered": []}
    h, a = _teams(fx)
    out: list[DataFragment] = []
    for team in (h, a):
        try:
            form = await runtime.context.sports.get_team_form(
                TeamRef(provider="api-football", id="0", name=team), 5
            )
            out.append(DataFragment(kind="form", payload=form.model_dump(mode="json")))
        except Exception:
            pass
    return {"gathered": out}


def _frag(state: CompanionState, kind: str) -> dict | None:
    for f in state.get("gathered", []) or []:
        if f.kind == kind:
            return f.payload
    return None


# ── orchestrator: data-dependent section plan ─────────────────────────────────
async def plan_briefing(state: CompanionState, runtime: Runtime[CompanionContext]) -> dict:
    fx_payload = _frag(state, "fixture")
    ref = ProviderRef(**fx_payload["ref"]) if fx_payload else ProviderRef(provider="api-football", id="0")
    h = fx_payload.get("home", {}).get("name") if fx_payload and fx_payload.get("home") else None
    a = fx_payload.get("away", {}).get("name") if fx_payload and fx_payload.get("away") else None
    h = h or (fx_payload.get("home_placeholder") if fx_payload else None) or "Home"
    a = a or (fx_payload.get("away_placeholder") if fx_payload else None) or "Away"
    title = f"{h} vs {a} — Match Briefing"

    sections: list[SectionSpec] = [
        SectionSpec(kind="stakes", title="Stakes", instructions="Explain what's on the line for both sides in plain language.", needs=["fixture", "standings"], order=0),
    ]
    if _frag(state, "lineups"):
        sections.append(SectionSpec(kind="key_players", title="Key Players", instructions="Highlight key players from the starting XIs and what to watch.", needs=["lineups"], order=1))
    if _frag(state, "h2h"):
        sections.append(SectionSpec(kind="head_to_head", title="Head-to-Head", instructions="Summarise the recent meetings and any pattern.", needs=["h2h"], order=2))
    sections.append(SectionSpec(kind="form_and_prediction", title="Form & Prediction", instructions="Summarise both teams' recent form and give a measured prediction with the market line if present.", needs=["form", "odds"], order=3))
    # bracket_impact only if the user has a stake
    uc = state.get("user_context")
    if uc and (uc.favorite_team_names or (runtime.context.extras or {}).get("has_bracket")):
        sections.append(SectionSpec(kind="bracket_impact", title="Your Bracket Impact", instructions="Explain how this result could affect the user's bracket and favorites.", needs=["fixture"], order=4))
    sections.append(SectionSpec(kind="how_it_works", title="How It Works", instructions="One short note on the relevant tournament/knockout rule for this stage.", needs=[], order=5))

    return {"briefing_plan": BriefingPlan(fixture_ref=ref, title=title, sections=sections)}


def fan_out_sections(state: CompanionState) -> list[Send]:
    plan = state["briefing_plan"]
    gathered = state.get("gathered", [])
    return [Send("write_section", {"spec": s, "gathered": gathered}) for s in plan.sections]


class _WorkerInput(TypedDict):
    spec: SectionSpec
    gathered: list[DataFragment]


async def write_section(payload: _WorkerInput) -> dict:
    spec = payload["spec"]
    gathered = payload["gathered"]
    ctx_bits = []
    for f in gathered:
        if f.kind in spec.needs:
            ctx_bits.append(f"[{f.kind}] {f.payload}")
    context_txt = "\n".join(ctx_bits)[:6000] or "(no extra data)"
    sys = SystemMessage(
        content=(
            "You write one short section of a football pre-match briefing. 2-4 sentences, plain "
            "language, grounded ONLY in the provided data. Do not invent specific numbers."
        )
    )
    human = HumanMessage(
        content=f"Section: {spec.title}\nInstructions: {spec.instructions}\nData:\n{context_txt}"
    )
    resp = await agent_model().ainvoke([sys, human])
    body = resp.content if isinstance(resp.content, str) else str(resp.content)
    return {
        "briefing_sections": [
            BriefingSection(kind=spec.kind, title=spec.title, body_markdown=body, order=spec.order)
        ]
    }


async def assemble(state: CompanionState) -> dict:
    plan = state["briefing_plan"]
    sections = sorted(state.get("briefing_sections", []), key=lambda s: s.order)
    md_parts = [f"# {plan.title}", ""]
    for s in sections:
        md_parts.append(f"## {s.title}\n\n{s.body_markdown}\n")
    markdown = "\n".join(md_parts).strip()
    briefing = Briefing(
        fixture_ref=plan.fixture_ref,
        title=plan.title,
        sections=sections,
        markdown=markdown,
        model="briefing-subgraph",
        generated_at=datetime.now(UTC),
    )
    return {
        "briefing": briefing,
        "final_response": markdown,
        "messages": [AIMessage(content=markdown)],
    }


def build_briefing_subgraph():
    b = StateGraph(CompanionState, context_schema=CompanionContext)
    for name, fn in (
        ("gather_fixture", gather_fixture),
        ("gather_lineups", gather_lineups),
        ("gather_standings", gather_standings),
        ("gather_odds", gather_odds),
        ("gather_h2h", gather_h2h),
        ("gather_form", gather_form),
    ):
        b.add_node(name, fn)
        b.add_edge(START, name)
        b.add_edge(name, "plan_briefing")
    b.add_node("plan_briefing", plan_briefing, defer=True)
    b.add_node("write_section", write_section, input_schema=_WorkerInput)
    b.add_node("assemble", assemble, defer=True)
    b.add_conditional_edges("plan_briefing", fan_out_sections, ["write_section"])
    b.add_edge("write_section", "assemble")
    b.add_edge("assemble", END)
    return b.compile()


briefing_subgraph = build_briefing_subgraph()
