"""Unit tests for the evolution analytics (pure functions)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.services import analytics as an
from app.services.scoring import ActivityInput

TODAY = date(2026, 9, 26)
KEYS = ["technical", "leadership", "research"]
W = {
    "project": {"technical": 1.0},
    "club_role": {"leadership": 1.0},
    "paper": {"research": 1.0, "technical": 0.3},
}
LABELS = {"technical": "Technical", "leadership": "Leadership", "research": "Research"}
TYPES = {"project": "Project", "club_role": "Club Role", "paper": "Paper"}


def act(id, type_key="project", start=TODAY, end=None, conf="self_reported", outcome="participant"):
    return ActivityInput(id, f"a{id}", type_key, start, end, outcome, "institute", conf)


def monthly(n, type_key="project", months_ago_start=0, every=1):
    """One activity every `every` months, from `months_ago_start` months ago up to n activities."""
    return [act(i, type_key, an.add_months(TODAY, -(months_ago_start - i * every))) for i in range(n)]


# ---------- helpers ----------
def test_add_months_clamps_day():
    assert an.add_months(date(2026, 3, 31), -1) == date(2026, 2, 28)
    assert an.add_months(date(2026, 1, 15), -13) == date(2024, 12, 15)


def test_slope():
    assert an.slope([0, 1, 2, 3]) == pytest.approx(1)
    assert an.slope([5, 5, 5]) == 0
    assert an.slope([7]) == 0


@pytest.mark.parametrize(
    ("values", "label"),
    [
        ([0, 0, 0, 1, 2, 3, 4], "inactive"),
        ([5, 8, 12, 16, 20, 25, 30], "emerging"),
        ([40, 42, 44, 46, 48, 50, 52], "improving"),
        ([50, 50, 51, 50, 51, 50, 51], "stable"),
        ([60, 57, 54, 51, 48, 45, 42], "declining"),
    ],
)
def test_classify(values, label):
    assert an.classify(values) == label


def test_classify_uses_only_last_window():
    assert an.classify([90, 10] + [50] * 7) == "stable"


# ---------- series & trends ----------
def test_series_empty_has_one_window_of_zeros():
    s = an.monthly_series([], W, KEYS, TODAY)
    assert len(s.dates) == 7 and s.dates[-1] == TODAY
    assert all(v == 0 for vals in s.scores.values() for v in vals)


def test_series_starts_month_before_first_activity_and_caps():
    s = an.monthly_series(monthly(1, months_ago_start=12), W, KEYS, TODAY)
    assert len(s.dates) == 14 and s.scores["technical"][0] == 0 and s.scores["technical"][1] > 0
    long = an.monthly_series(monthly(1, months_ago_start=60), W, KEYS, TODAY, max_months=36)
    assert len(long.dates) == 37


def test_series_matches_replay_and_rises_with_activity():
    s = an.monthly_series(monthly(12, months_ago_start=11), W, KEYS, TODAY)
    tech = s.scores["technical"]
    assert tech == sorted(tech) and tech[-1] > 0


def test_trends_improving_then_declining():
    rising = an.trends(an.monthly_series(monthly(12, months_ago_start=11), W, KEYS, TODAY))
    assert rising["technical"].label in {"improving", "emerging"} and rising["technical"].change > 0
    old = [act(i, start=an.add_months(TODAY, -(18 - i))) for i in range(10)]  # active 18→9 months ago, then nothing
    falling = an.trends(an.monthly_series(old, W, KEYS, TODAY))["technical"]
    assert falling.label == "declining" and falling.change < 0
    assert rising["leadership"].label == "inactive"


# ---------- position ----------
def test_percentile():
    assert an.percentile(50, []) is None
    assert an.percentile(50, [10, 20, 60, 70]) == 50
    assert an.percentile(50, [50, 50]) == 50
    assert an.percentile(100, [1, 2, 3]) == 100


def test_strengths_and_gaps():
    s, g = an.strengths_and_gaps({"a": 80, "b": 60, "c": 20, "d": 10, "e": 5})
    assert s == ["a", "b"] and g == ["e", "d", "c"]


# ---------- recommendations ----------
def test_gain_from_new_activity_targets_mapped_competency():
    g = an.gain_from_new_activity([act(1)], "paper", W, KEYS, TODAY)
    assert g["research"] > g["technical"] > 0 and g["leadership"] == 0


def test_recommendations_cover_gap_declining_and_evidence():
    acts = [act(1, "club_role", start=an.add_months(TODAY, -20), end=an.add_months(TODAY, -8), conf="verified")]
    acts += [act(10 + i, start=an.add_months(TODAY, -i)) for i in range(4)]  # recent self-reported projects
    series = an.monthly_series(acts, W, KEYS, TODAY)
    tr = an.trends(series)
    _, gaps = an.strengths_and_gaps({k: t.score for k, t in tr.items()})
    recs = an.recommendations(acts, W, KEYS, LABELS, TYPES, tr, gaps, TODAY)
    kinds = {r.kind for r in recs}
    assert {"gap", "evidence"} <= kinds
    assert [r.gain for r in recs] == sorted([r.gain for r in recs], reverse=True)
    research = next(r for r in recs if r.competency == "research")
    assert research.activity_types[0] == "paper" and "Paper" in research.detail
    evidence = next(r for r in recs if r.kind == "evidence")
    assert sorted(evidence.activity_ids) == [10, 11, 12, 13]
    if tr["leadership"].label == "declining" and "leadership" not in gaps:
        lead = next(r for r in recs if r.kind == "declining")
        assert lead.activity_ids == [1]


def test_no_recommendations_without_activities():
    assert an.recommendations([], W, KEYS, LABELS, TYPES, {}, [], TODAY) == []


# ---------- timeline ----------
def test_timeline_newest_first_with_diminishing_deltas():
    acts = [act(i, start=TODAY - timedelta(days=3 - i)) for i in range(3)]
    tl = an.timeline(acts, W, KEYS, TODAY)
    assert [e.activity_id for e in tl] == [2, 1, 0]
    deltas = [e.deltas["technical"] for e in reversed(tl)]
    assert deltas[0] > deltas[1] > deltas[2] > 0  # saturation: each later one adds a bit less
    assert set(tl[0].deltas) == {"technical"}


# ---------- interest drift ----------
def _at(days_ago):
    return datetime(2026, 9, 26, tzinfo=UTC) - timedelta(days=days_ago)


def test_interest_drift():
    recs = [
        an.InterestRecord("Web Development", 4, _at(500), _at(100)),
        an.InterestRecord("Algorithms", 3, _at(500), None),
        an.InterestRecord("Cloud Computing", 5, _at(90), None),
        an.InterestRecord("devops", 4, _at(60), None),
    ]
    d = an.interest_drift(recs, _at(0))
    assert d.then == ["Algorithms", "Web Development"]
    assert d.now == ["Algorithms", "Cloud Computing", "devops"]
    assert d.added == ["Cloud Computing", "devops"] and d.removed == ["Web Development"]
    assert d.drift == pytest.approx(1 - 1 / 4)


def test_interest_drift_short_history_uses_first_record_and_empty():
    d = an.interest_drift([an.InterestRecord("ML", 3, _at(10), None)], _at(0))
    assert d.then == d.now == ["ML"] and d.drift == 0
    assert an.interest_drift([], _at(0)).drift is None
