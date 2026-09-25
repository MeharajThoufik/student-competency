"""Unit tests for the pure scoring engine."""

import math
from datetime import date, timedelta

import pytest

from app.services.scoring import (
    DEFAULT_PARAMS,
    ActivityInput,
    compute_scores,
    decay_factor,
    duration_factor,
    saturate,
)

TODAY = date(2026, 9, 25)
KEYS = ["technical", "leadership"]
W = {"project": {"technical": 1.0, "leadership": 0.0}, "club_role": {"technical": 0.0, "leadership": 1.0}}


def act(
    id=1, type_key="project", start=TODAY, end=None, outcome="participant", scope="institute", conf="self_reported"
) -> ActivityInput:
    return ActivityInput(id, f"a{id}", type_key, start, end, outcome, scope, conf)


def test_no_activities_scores_zero():
    scores = compute_scores([], W, KEYS, TODAY)
    assert all(s.score == 0 and s.raw == 0 for s in scores.values())


def test_single_activity_math():
    s = compute_scores([act()], W, KEYS, TODAY)["technical"]
    # weight 1 × level 1 × conf 0.5 × decay 1
    assert s.raw == pytest.approx(0.5)
    assert s.score == pytest.approx(100 * (1 - math.exp(-0.5 / DEFAULT_PARAMS.k)))


def test_zero_weight_contributes_nothing():
    s = compute_scores([act()], W, KEYS, TODAY)["leadership"]
    assert s.raw == 0 and s.contributions == []


def test_confidence_ordering():
    raws = [
        compute_scores([act(conf=c)], W, KEYS, TODAY)["technical"].raw
        for c in ("rejected", "self_reported", "evidence_attached", "verified")
    ]
    assert raws == sorted(raws) and len(set(raws)) == 4


def test_decay_halves_at_half_life():
    a = act(start=TODAY - timedelta(days=round(12 * 30.4375)))
    assert decay_factor(a, TODAY) == pytest.approx(0.5, abs=0.01)


def test_ongoing_activity_does_not_decay():
    a = act(start=TODAY - timedelta(days=400), end=TODAY + timedelta(days=30))
    assert decay_factor(a, TODAY) == 1.0


def test_future_activity_ignored():
    s = compute_scores([act(start=TODAY + timedelta(days=1))], W, KEYS, TODAY)["technical"]
    assert s.raw == 0


def test_as_of_replays_history():
    old = act(1, start=date(2025, 1, 10))
    new = act(2, start=date(2026, 6, 1))
    past = compute_scores([old, new], W, KEYS, date(2025, 6, 1))["technical"]
    assert [c.activity_id for c in past.contributions] == [1]


def test_duration_factor_grows_then_caps():
    one_day = duration_factor(act(), TODAY)
    three_months = duration_factor(act(start=TODAY - timedelta(days=91), end=TODAY), TODAY)
    five_years = duration_factor(act(start=TODAY - timedelta(days=1826), end=TODAY), TODAY)
    assert one_day == 1.0
    assert 1.4 < three_months < 1.6
    assert five_years == DEFAULT_PARAMS.duration_cap


def test_outcome_and_scope_multiply():
    base = compute_scores([act()], W, KEYS, TODAY)["technical"].raw
    top = compute_scores([act(outcome="winner", scope="international")], W, KEYS, TODAY)["technical"].raw
    assert top == pytest.approx(base * 2.0 * 1.8)


def test_saturation_bounded_and_monotonic():
    values = [saturate(r) for r in (0, 1, 5, 20, 100)]
    assert values == sorted(values)
    assert values[0] == 0 and values[-1] < 100


def test_breakdown_sums_to_raw_and_is_sorted():
    acts = [act(i, start=TODAY - timedelta(days=30 * i), conf="verified") for i in range(1, 6)]
    s = compute_scores(acts, W, KEYS, TODAY)["technical"]
    assert sum(c.points for c in s.contributions) == pytest.approx(s.raw)
    points = [c.points for c in s.contributions]
    assert points == sorted(points, reverse=True)
    assert s.contributions[0].activity_id == 1  # most recent decays least


def test_activities_route_to_their_competencies():
    scores = compute_scores([act(1), act(2, type_key="club_role")], W, KEYS, TODAY)
    assert [c.activity_id for c in scores["technical"].contributions] == [1]
    assert [c.activity_id for c in scores["leadership"].contributions] == [2]
