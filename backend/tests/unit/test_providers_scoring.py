from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.providers.base import (
    SportsDataProvider,
    TeamRef,
    TournamentRef,
    WinProbabilities,
    devig_three_way,
)
from app.providers.fake import FakeProvider
from app.services.scoring_service import DEFAULT_SCORING, score_pick

TREF = TournamentRef(provider="fake", league="1", season="2026")


def test_devig_sums_to_one():
    h, d, a = devig_three_way(1.97, 3.6, 3.6)
    assert abs((h + d + a) - 1.0) < 1e-9
    assert h > a  # netherlands favourite


def test_fake_provider_satisfies_protocol():
    assert isinstance(FakeProvider(), SportsDataProvider)


@pytest.mark.asyncio
async def test_fake_fixtures_and_live():
    p = FakeProvider()
    fixtures = await p.list_fixtures(TREF)
    assert len(fixtures) >= 2
    live = await p.get_live_state(fixtures[0].ref)
    assert live.status in {"1H", "HT", "2H", "NS"}


@pytest.mark.asyncio
async def test_fake_win_probabilities_valid():
    p = FakeProvider()
    wp: WinProbabilities = await p.get_win_probabilities(
        TeamRef(provider="o", id="0", name="Netherlands"),
        TeamRef(provider="o", id="0", name="Japan"),
    )
    assert 0.0 <= wp.home <= 1.0
    assert wp.devig is True


def test_score_pick_correct_winner_and_exact():
    fx = SimpleNamespace(winner_team_id="NED", home_score=2, away_score=1)
    pick = SimpleNamespace(
        predicted_winner_team_id="NED", predicted_team_id=None,
        predicted_home_score=2, predicted_away_score=1,
    )
    pts, correct = score_pick(pick, fx, DEFAULT_SCORING)  # type: ignore[arg-type]
    assert correct is True
    assert pts == DEFAULT_SCORING["correct_winner"] + DEFAULT_SCORING["exact_score"]


def test_score_pick_wrong_winner():
    fx = SimpleNamespace(winner_team_id="JPN", home_score=0, away_score=1)
    pick = SimpleNamespace(
        predicted_winner_team_id="NED", predicted_team_id=None,
        predicted_home_score=None, predicted_away_score=None,
    )
    pts, correct = score_pick(pick, fx, DEFAULT_SCORING)  # type: ignore[arg-type]
    assert correct is False
    assert pts == 0
