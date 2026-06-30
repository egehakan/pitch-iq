from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from app.graph.build import compile_graph
from app.graph.state import CompanionContext
from app.providers.base import TournamentRef
from app.providers.fake import FakeProvider


@pytest.fixture
def fake_providers():
    p = FakeProvider()
    return p, p


@pytest.fixture
def context(fake_providers):
    sports, odds = fake_providers
    return CompanionContext(
        sports=sports,
        odds=odds,
        extras={"tournament_ref": TournamentRef(provider="fake", league="1", season="2026")},
    )


@pytest.fixture
def graph():
    return compile_graph(checkpointer=InMemorySaver(), store=InMemoryStore())
