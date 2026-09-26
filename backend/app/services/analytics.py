"""Evolution analytics built on the scoring engine (pure functions, no database access).

Everything is derived by replaying the scoring engine at past dates, so any value shown to a
learner can be recomputed and explained:

    series           score of every competency at monthly points (as_of replay)
    trend            label from the last `window` months: OLS slope + level rules
    strengths/gaps   highest and lowest current competencies
    recommendations  counterfactuals: "what would this activity / this evidence add?"
    timeline         marginal score gain of each activity at the time it was completed
    interest drift   Jaccard distance between the interest set then and now
"""

import calendar
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta

from app.services.scoring import DEFAULT_PARAMS, ActivityInput, ScoringParams, compute_scores

Weights = dict[str, dict[str, float]]


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


# ---------- Trend classification ----------
@dataclass(frozen=True)
class TrendParams:
    window_months: int = 6
    slope_threshold: float = 1.0  # score points per month (≈ ±6 over the window)
    emerging_from: float = 15.0  # below this at the start of the window …
    emerging_to: float = 25.0  # … and at least this now
    inactive_below: float = 5.0  # never reached this within the window


DEFAULT_TREND = TrendParams()
TREND_LABELS = ("emerging", "improving", "stable", "declining", "inactive")


def slope(values: list[float]) -> float:
    """Least-squares slope per step."""
    n = len(values)
    if n < 2:
        return 0.0
    xm, ym = (n - 1) / 2, sum(values) / n
    num = sum((i - xm) * (v - ym) for i, v in enumerate(values))
    den = sum((i - xm) ** 2 for i in range(n))
    return num / den


def classify(values: list[float], p: TrendParams = DEFAULT_TREND) -> str:
    window = values[-(p.window_months + 1) :]
    prev, now, s = window[0], window[-1], slope(window)
    if max(window) < p.inactive_below:
        return "inactive"
    if prev < p.emerging_from and now >= p.emerging_to:
        return "emerging"
    if s >= p.slope_threshold:
        return "improving"
    if s <= -p.slope_threshold:
        return "declining"
    return "stable"


@dataclass
class Series:
    dates: list[date]
    scores: dict[str, list[float]]


def monthly_series(
    activities: list[ActivityInput],
    weights: Weights,
    keys: list[str],
    today: date,
    max_months: int = 36,
    trend: TrendParams = DEFAULT_TREND,
    params: ScoringParams = DEFAULT_PARAMS,
) -> Series:
    """Scores at today, today−1 month, … back to the month before the first activity (≥ one trend window)."""
    span = 0
    if activities:
        first = min(a.start_date for a in activities)
        span = (today.year - first.year) * 12 + today.month - first.month + 1
    n = min(max_months, max(trend.window_months, span))
    dates = [add_months(today, -k) for k in range(n, -1, -1)]
    scores: dict[str, list[float]] = {k: [] for k in keys}
    for d in dates:
        for k, s in compute_scores(activities, weights, keys, d, params).items():
            scores[k].append(round(s.score, 2))
    return Series(dates, scores)


@dataclass
class Trend:
    key: str
    score: float
    previous: float
    change: float
    slope: float
    label: str


def trends(series: Series, p: TrendParams = DEFAULT_TREND) -> dict[str, Trend]:
    out = {}
    for k, values in series.scores.items():
        window = values[-(p.window_months + 1) :]
        out[k] = Trend(
            key=k,
            score=window[-1],
            previous=window[0],
            change=round(window[-1] - window[0], 2),
            slope=round(slope(window), 3),
            label=classify(values, p),
        )
    return out


# ---------- Position ----------
def percentile(value: float, others: list[float]) -> float | None:
    """Share of the cohort scoring below `value` (ties count half)."""
    if not others:
        return None
    below = sum(o < value for o in others)
    equal = sum(o == value for o in others)
    return round(100 * (below + 0.5 * equal) / len(others), 1)


def strengths_and_gaps(scores: dict[str, float], n: int = 3, min_strength: float = 30.0) -> tuple[list[str], list[str]]:
    ranked = sorted(scores, key=lambda k: scores[k], reverse=True)
    strengths = [k for k in ranked[:n] if scores[k] >= min_strength]
    gaps = [k for k in reversed(ranked) if k not in strengths][:n]
    return strengths, gaps


# ---------- Recommendations ----------
@dataclass
class Recommendation:
    kind: str  # gap | declining | evidence
    competency: str | None
    title: str
    detail: str
    gain: float
    activity_types: list[str] = field(default_factory=list)
    activity_ids: list[int] = field(default_factory=list)


def _totals(activities: list[ActivityInput], weights: Weights, keys: list[str], today: date, params: ScoringParams):
    return {k: s.score for k, s in compute_scores(activities, weights, keys, today, params).items()}


def gain_from_new_activity(
    activities: list[ActivityInput],
    type_key: str,
    weights: Weights,
    keys: list[str],
    today: date,
    params: ScoringParams = DEFAULT_PARAMS,
) -> dict[str, float]:
    """Score change if the learner completed one typical activity of this type today (with evidence)."""
    new = ActivityInput(-1, "(new)", type_key, today, None, "participant", "institute", "evidence_attached")
    before = _totals(activities, weights, keys, today, params)
    after = _totals([*activities, new], weights, keys, today, params)
    return {k: after[k] - before[k] for k in keys}


def _best_option(activities, comp, weights, keys, today, params) -> tuple[str, float, list[str]]:
    types = sorted((t for t in weights if weights[t].get(comp, 0) > 0), key=lambda t: weights[t][comp], reverse=True)[:2]
    gains = {t: gain_from_new_activity(activities, t, weights, keys, today, params)[comp] for t in types}
    best = max(gains, key=lambda t: gains[t])
    return best, gains[best], types


def recommendations(
    activities: list[ActivityInput],
    weights: Weights,
    keys: list[str],
    labels: dict[str, str],
    type_labels: dict[str, str],
    trend_by_key: dict[str, Trend],
    gaps: list[str],
    today: date,
    params: ScoringParams = DEFAULT_PARAMS,
    trend: TrendParams = DEFAULT_TREND,
    limit: int = 5,
) -> list[Recommendation]:
    if not activities:
        return []
    recs: list[Recommendation] = []

    for comp in gaps[:2]:
        t, g, types = _best_option(activities, comp, weights, keys, today, params)
        others = [type_labels.get(x, x) for x in types if x != t]
        recs.append(
            Recommendation(
                kind="gap",
                competency=comp,
                title=f"Build {labels[comp]}",
                detail=f"{labels[comp]} is one of your lowest competencies. One {type_labels.get(t, t)} with evidence "
                f"would add about +{g:.1f}" + (f"; {others[0]} also helps." if others else "."),
                gain=round(g, 2),
                activity_types=types,
            )
        )

    declining = [k for k, tr in trend_by_key.items() if tr.label == "declining" and k not in gaps]
    for comp in sorted(declining, key=lambda k: trend_by_key[k].change)[:2]:
        t, g, types = _best_option(activities, comp, weights, keys, today, params)
        developing = [a for a in activities if weights.get(a.type_key, {}).get(comp, 0) > 0]
        last = max(developing, key=lambda a: a.end_date or a.start_date, default=None)
        since = f"; your last activity developing it was “{last.title}” ({last.end_date or last.start_date})" if last else ""
        recs.append(
            Recommendation(
                kind="declining",
                competency=comp,
                title=f"Refresh {labels[comp]}",
                detail=f"{labels[comp]} fell {abs(trend_by_key[comp].change):.1f} points in the last "
                f"{trend.window_months} months{since}. Scores halve every {params.half_life_months:g} months without "
                f"new activity; one {type_labels.get(t, t)} would add about +{g:.1f}.",
                gain=round(g, 2),
                activity_types=types,
                activity_ids=[last.id] if last else [],
            )
        )

    self_reported = [a for a in activities if a.confidence_key == "self_reported"]
    if self_reported:
        upgraded = [replace(a, confidence_key="evidence_attached") if a.confidence_key == "self_reported" else a for a in activities]
        before = _totals(activities, weights, keys, today, params)
        after = _totals(upgraded, weights, keys, today, params)
        comp = max(keys, key=lambda k: after[k] - before[k])
        g = after[comp] - before[comp]
        if g >= 0.1:
            n = len(self_reported)
            recs.append(
                Recommendation(
                    kind="evidence",
                    competency=comp,
                    title="Attach evidence to self-reported activities",
                    detail=f"{n} {'activity has' if n == 1 else 'activities have'} no certificate or proof. Attaching "
                    f"evidence raises their weight from ×{params.confidence['self_reported']:g} to "
                    f"×{params.confidence['evidence_attached']:g}, adding up to +{g:.1f} to {labels[comp]}.",
                    gain=round(g, 2),
                    activity_ids=[a.id for a in self_reported],
                )
            )

    recs.sort(key=lambda r: r.gain, reverse=True)
    return recs[:limit]


# ---------- Learning timeline ----------
@dataclass
class TimelineEntry:
    activity_id: int
    title: str
    type_key: str
    start_date: date
    end_date: date | None
    confidence_key: str
    deltas: dict[str, float]  # competency -> score gained, at the time the activity was completed


def timeline(
    activities: list[ActivityInput], weights: Weights, keys: list[str], today: date, params: ScoringParams = DEFAULT_PARAMS
) -> list[TimelineEntry]:
    """Newest first. Each delta is the activity's marginal effect given everything done before it."""
    ordered = sorted(activities, key=lambda a: (a.start_date, a.id))
    out = []
    for i, a in enumerate(ordered):
        at = min(a.end_date or a.start_date, today)
        before = _totals(ordered[:i], weights, keys, at, params)
        after = _totals(ordered[: i + 1], weights, keys, at, params)
        deltas = {k: round(after[k] - before[k], 2) for k in keys if after[k] - before[k] >= 0.05}
        out.append(TimelineEntry(a.id, a.title, a.type_key, a.start_date, a.end_date, a.confidence_key, deltas))
    return out[::-1]


# ---------- Interest drift ----------
@dataclass(frozen=True)
class InterestRecord:
    tag: str
    level: int
    created_at: datetime
    removed_at: datetime | None


@dataclass
class InterestDrift:
    since: datetime | None
    then: list[str]
    now: list[str]
    added: list[str]
    removed: list[str]
    drift: float | None  # Jaccard distance 0 (same) … 1 (completely different)


def _active_at(records: list[InterestRecord], t: datetime) -> dict[str, str]:
    return {
        r.tag.lower(): r.tag for r in records if r.created_at <= t and (r.removed_at is None or r.removed_at > t)
    }


def jaccard_distance(a: set[str], b: set[str]) -> float | None:
    union = a | b
    return None if not union else round(1 - len(a & b) / len(union), 3)


def interest_drift(records: list[InterestRecord], now: datetime, months: int = 12) -> InterestDrift:
    """Compare interests `months` ago (or when first recorded, if later) with today."""
    if not records:
        return InterestDrift(None, [], [], [], [], None)
    since = max(now - timedelta(days=round(months * 30.4375)), min(r.created_at for r in records))
    then, current = _active_at(records, since), _active_at(records, now)
    return InterestDrift(
        since=since,
        then=sorted(then.values()),
        now=sorted(current.values()),
        added=sorted(current[k] for k in current.keys() - then.keys()),
        removed=sorted(then[k] for k in then.keys() - current.keys()),
        drift=jaccard_distance(set(then), set(current)),
    )
