"""Graph state schema: CompanionState TypedDict + strict Pydantic payloads + run context.

(canonical-spec §3.1) Graph state is a TypedDict so Annotated reducer channels work;
all nested payloads and tool I/O are strict Pydantic BaseModel (extra='forbid').
"""
from __future__ import annotations

import operator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal, NotRequired

from langchain.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import TypedDict

from app.providers.base import (
    DataFragment,
    OddsProvider,
    ProviderRef,
    SportsDataProvider,
    WinProbabilities,
)


class Route(str, Enum):
    MATCH_QA = "match_qa"
    RULES_QA = "rules_qa"
    BRACKET_QA = "bracket_qa"
    PREDICTION = "prediction"
    BRIEFING = "briefing"
    BRACKET_OPS = "bracket_ops"
    CHITCHAT = "chitchat"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── router output (OpenAI strict json_schema, enum-closed) ───────────────────
class RouterDecision(_Strict):
    route: Route
    confidence: float = Field(ge=0.0, le=1.0)
    params: dict[str, str] = Field(default_factory=dict)
    rationale: str | None = None


# ── durable cross-thread user facts (from Store at ingest) ───────────────────
class UserContext(_Strict):
    user_id: str
    favorite_team_ids: list[str] = Field(default_factory=list)
    favorite_team_names: list[str] = Field(default_factory=list)
    tone: Literal["concise", "detailed"] = "concise"
    locale: str = "en"
    timezone: str = "UTC"
    notes: list[str] = Field(default_factory=list)


# ── prediction (generator–evaluator) ─────────────────────────────────────────
class Prediction(_Strict):
    fixture_ref: ProviderRef
    probabilities: WinProbabilities
    scoreline: str
    drivers: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    round: int = 0


class Critique(_Strict):
    verdict: Literal["pass", "revise"]
    issues: list[str] = Field(default_factory=list)
    market_delta: float | None = None
    favorite_bias_flag: bool = False


# ── briefing (orchestrator–worker map-reduce) ────────────────────────────────
SectionKind = Literal[
    "stakes", "key_players", "bracket_impact", "head_to_head", "form_and_prediction", "how_it_works"
]


class SectionSpec(_Strict):
    kind: SectionKind
    title: str
    instructions: str
    needs: list[str] = Field(default_factory=list)
    order: int = 0


class BriefingPlan(_Strict):
    fixture_ref: ProviderRef
    title: str = "Match Briefing"
    sections: list[SectionSpec] = Field(default_factory=list)


class BriefingSection(_Strict):
    kind: str
    title: str
    body_markdown: str
    order: int = 0


class Briefing(_Strict):
    fixture_ref: ProviderRef
    title: str
    sections: list[BriefingSection] = Field(default_factory=list)
    markdown: str = ""
    model: str = ""
    generated_at: datetime | None = None


# ── bracket HITL ─────────────────────────────────────────────────────────────
class BracketChange(_Strict):
    bracket_id: str
    action: Literal["submit", "lock", "edit_picks"]
    summary: str
    diff: list[str] = Field(default_factory=list)
    pick_updates: list[dict[str, Any]] | None = None


# ── the graph state ──────────────────────────────────────────────────────────
class CompanionState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_id: str
    tournament_id: str
    thread_id: NotRequired[str]
    route: NotRequired[Route]
    intent: NotRequired[RouterDecision]
    user_context: NotRequired[UserContext]
    gathered: Annotated[list[DataFragment], operator.add]
    prediction: NotRequired[Prediction]
    critique: NotRequired[Critique]
    prediction_round: NotRequired[int]
    briefing_plan: NotRequired[BriefingPlan]
    briefing_sections: Annotated[list[BriefingSection], operator.add]
    briefing: NotRequired[Briefing]
    pending_change: NotRequired[BracketChange]
    approved: NotRequired[bool]
    final_response: NotRequired[str]


@dataclass
class CompanionContext:
    """Run-scoped deps injected at invoke via context=...; nodes reach via runtime.context."""

    sports: SportsDataProvider
    odds: OddsProvider
    user_tz: str = "UTC"
    # Optional callable injected by the API layer for bracket tools/ops (DB-backed).
    bracket_reader: Any = None
    bracket_writer: Any = None
    extras: dict[str, Any] = field(default_factory=dict)
