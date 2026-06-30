"""Patterns 3 + 5 — prediction subgraph (parallel gen∥market + generator–evaluator).

START → [gen_prediction ∥ fetch_market] → critic → (revise? loop ≤2 : finalize) → END
The critic pressure-tests the model probabilities against the no-vig market line and
form so predictions aren't naive. Hard cap: ≤ 2 revision rounds. (canonical-spec §3.5)
"""
from __future__ import annotations

from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from pydantic import BaseModel, ConfigDict, Field

from app.graph.llm import critic_model
from app.graph.state import (
    CompanionContext,
    CompanionState,
    Critique,
    Prediction,
)
from app.providers.base import (
    DataFragment,
    Fixture,
    ProviderRef,
    TeamForm,
    TeamRef,
    WinProbabilities,
)


class _PredictionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prob_home: float = Field(ge=0.0, le=1.0)
    prob_draw: float = Field(ge=0.0, le=1.0)
    prob_away: float = Field(ge=0.0, le=1.0)
    scoreline: str
    drivers: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _resolve_teams(state: CompanionState, fixtures: list[Fixture]) -> tuple[str, str, ProviderRef | None]:
    intent = state.get("intent")
    params = intent.params if intent else {}
    a = params.get("team_a") or params.get("team") or ""
    b = params.get("team_b") or ""
    # try to find a fixture involving a (and b)
    for fx in fixtures:
        names = [t.name for t in (fx.home, fx.away) if t]
        joined = " ".join(_norm(n) for n in names)
        if a and _norm(a) in joined and (not b or _norm(b) in joined):
            hn = fx.home.name if fx.home else (fx.home_placeholder or "Home")
            an = fx.away.name if fx.away else (fx.away_placeholder or "Away")
            return hn, an, fx.ref
    if a and b:
        return a, b, None
    if fixtures:
        fx = fixtures[0]
        hn = fx.home.name if fx.home else (fx.home_placeholder or "Home")
        an = fx.away.name if fx.away else (fx.away_placeholder or "Away")
        return hn, an, fx.ref
    return a or "Home", b or "Away", None


async def gen_prediction(state: CompanionState, runtime: Runtime[CompanionContext]) -> dict:
    sports = runtime.context.sports
    tref = (runtime.context.extras or {}).get("tournament_ref")
    try:
        fixtures = await sports.list_fixtures(tref) if tref else []
    except Exception:
        fixtures = []
    home, away, ref = _resolve_teams(state, fixtures)
    ref = ref or ProviderRef(provider="api-football", id="0")

    # ground in form (best-effort)
    form_txt = ""
    for team in (home, away):
        try:
            f: TeamForm = await sports.get_team_form(TeamRef(provider="api-football", id="0", name=team), 5)
            form_txt += f"\n{team} form: {f.wdl or 'n/a'}"
        except Exception:
            pass

    # market line, if already fetched in parallel
    market = _market_from_state(state)
    market_txt = (
        f"\nNo-vig market line: home {market.home:.2f}, draw {market.draw:.2f}, away {market.away:.2f}"
        if market
        else "\nNo market line available."
    )
    rnd = state.get("prediction_round", 0)
    prior = state.get("critique")
    revise_txt = ""
    if prior and prior.verdict == "revise":
        revise_txt = "\nThe critic asked you to revise: " + "; ".join(prior.issues)

    sys = SystemMessage(
        content=(
            "You are a football match predictor. Output 3-way win probabilities that SUM TO 1, "
            "a likely scoreline, and 2-4 concrete drivers grounded in form/H2H (not vibes). "
            "Stay close to the market line if one is given; do not be naively favorite-biased."
        )
    )
    human = HumanMessage(
        content=f"Predict {home} vs {away}.{form_txt}{market_txt}{revise_txt}"
    )
    draft: _PredictionDraft = await critic_model().with_structured_output(
        _PredictionDraft, method="function_calling"
    ).ainvoke([sys, human])
    total = draft.prob_home + draft.prob_draw + draft.prob_away or 1.0
    probs = WinProbabilities(
        home=draft.prob_home / total,
        draw=draft.prob_draw / total,
        away=draft.prob_away / total,
        source="model",
        devig=False,
    )
    pred = Prediction(
        fixture_ref=ref,
        probabilities=probs,
        scoreline=draft.scoreline,
        drivers=draft.drivers,
        confidence=draft.confidence,
        round=rnd,
    )
    return {"prediction": pred, "prediction_round": rnd + 1}


def _market_from_state(state: CompanionState) -> WinProbabilities | None:
    for frag in state.get("gathered", []) or []:
        if frag.kind == "market":
            try:
                return WinProbabilities(**frag.payload)
            except Exception:
                return None
    return None


async def fetch_market(state: CompanionState, runtime: Runtime[CompanionContext]) -> dict:
    odds = runtime.context.odds
    sports = runtime.context.sports
    tref = (runtime.context.extras or {}).get("tournament_ref")
    try:
        fixtures = await sports.list_fixtures(tref) if tref else []
    except Exception:
        fixtures = []
    home, away, _ = _resolve_teams(state, fixtures)
    try:
        probs = await odds.get_win_probabilities(
            TeamRef(provider="odds", id="0", name=home),
            TeamRef(provider="odds", id="0", name=away),
        )
        return {"gathered": [DataFragment(kind="market", payload=probs.model_dump())]}
    except Exception:
        return {"gathered": []}


async def critic(state: CompanionState, runtime: Runtime[CompanionContext]) -> dict:
    pred = state["prediction"]
    p = pred.probabilities
    issues: list[str] = []
    s = p.home + p.draw + p.away
    if abs(s - 1.0) > 0.02:
        issues.append(f"probabilities sum to {s:.3f}, not 1")
    for name, v in (("home", p.home), ("draw", p.draw), ("away", p.away)):
        if not (0.0 <= v <= 1.0):
            issues.append(f"{name} probability {v} out of range")
    market = _market_from_state(state)
    market_delta = None
    if market:
        market_delta = max(abs(p.home - market.home), abs(p.draw - market.draw), abs(p.away - market.away))
        if market_delta > 0.20:
            issues.append(
                f"model diverges from market by {market_delta:.2f} (>0.20) — justify or move toward the line"
            )
    favorite_bias = max(p.home, p.away) > 0.85 and not pred.drivers
    if favorite_bias:
        issues.append("looks favorite-biased with no concrete drivers")
    verdict = "revise" if issues and state.get("prediction_round", 0) < 2 else "pass"
    return {
        "critique": Critique(
            verdict=verdict,
            issues=issues,
            market_delta=market_delta,
            favorite_bias_flag=favorite_bias,
        )
    }


def after_critic(state: CompanionState) -> str:
    c = state["critique"]
    if c.verdict == "revise" and state.get("prediction_round", 0) < 2:
        return "gen_prediction"
    return "finalize"


async def finalize(state: CompanionState) -> dict:
    pred = state["prediction"]
    p = pred.probabilities
    market = _market_from_state(state)
    h = pred.fixture_ref
    lines = [
        "**Prediction**",
        f"- Win probabilities — home {p.home:.0%}, draw {p.draw:.0%}, away {p.away:.0%}",
        f"- Most likely scoreline: {pred.scoreline}",
        "- Drivers: " + ("; ".join(pred.drivers) if pred.drivers else "n/a"),
    ]
    if market:
        lines.append(
            f"- Market (no-vig): home {market.home:.0%}, draw {market.draw:.0%}, away {market.away:.0%} (source {market.source})"
        )
    lines.append("\n_Odds shown for context only. 18+ — Gamble Responsibly._")
    text = "\n".join(lines)
    _ = h
    return {"final_response": text, "messages": [AIMessage(content=text)]}


def build_prediction_subgraph():
    b = StateGraph(CompanionState, context_schema=CompanionContext)
    b.add_node("gen_prediction", gen_prediction)
    b.add_node("fetch_market", fetch_market)
    b.add_node("critic", critic)
    b.add_node("finalize", finalize)
    b.add_edge(START, "gen_prediction")
    b.add_edge(START, "fetch_market")
    b.add_edge("gen_prediction", "critic")
    b.add_edge("fetch_market", "critic")
    b.add_conditional_edges("critic", after_critic, ["gen_prediction", "finalize"])
    b.add_edge("finalize", END)
    return b.compile()


prediction_subgraph = build_prediction_subgraph()
