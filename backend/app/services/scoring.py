"""Competency scoring engine (pure functions, no database access).

For activity a and competency c:

    contrib(a, c) = W[type(a), c] × level(a) × conf(a) × decay(a)

    level(a) = outcome_factor × scope_factor × duration_factor
    conf(a)  = evidence confidence (self-reported < evidence attached < educator-verified)
    decay(a) = 0.5 ** (months since the activity ended / half-life)

    raw_c    = Σ_a contrib(a, c)
    score_c  = 100 × (1 − e^(−raw_c / k))        saturating, 0 ≤ score < 100

Every factor is returned in the breakdown so each score is explainable.
"""

import math
from dataclasses import dataclass, field
from datetime import date

AVG_DAYS_PER_MONTH = 30.4375


@dataclass(frozen=True)
class ScoringParams:
    half_life_months: float = 12.0
    k: float = 5.0
    confidence: dict[str, float] = field(
        default_factory=lambda: {"self_reported": 0.5, "evidence_attached": 0.8, "verified": 1.0, "rejected": 0.25}
    )
    outcome: dict[str, float] = field(
        default_factory=lambda: {
            "participant": 1.0,
            "completed": 1.0,
            "contributor": 1.2,
            "lead": 1.5,
            "finalist": 1.5,
            "winner": 2.0,
        }
    )
    scope: dict[str, float] = field(
        default_factory=lambda: {"personal": 0.8, "institute": 1.0, "state": 1.2, "national": 1.5, "international": 1.8}
    )
    # duration_factor = 1 + duration_slope × log2(1 + months), capped
    duration_slope: float = 0.25
    duration_cap: float = 2.0


DEFAULT_PARAMS = ScoringParams()


@dataclass(frozen=True)
class ActivityInput:
    id: int
    title: str
    type_key: str
    start_date: date
    end_date: date | None
    outcome: str
    scope: str
    confidence_key: str  # self_reported | evidence_attached | verified | rejected


@dataclass(frozen=True)
class Contribution:
    activity_id: int
    title: str
    type_key: str
    date: date
    weight: float
    level: float
    confidence: float
    decay: float
    points: float


@dataclass
class CompetencyScore:
    key: str
    score: float
    raw: float
    contributions: list[Contribution]


def months_between(earlier: date, later: date) -> float:
    return max(0.0, (later - earlier).days / AVG_DAYS_PER_MONTH)


def duration_factor(a: ActivityInput, as_of: date, p: ScoringParams = DEFAULT_PARAMS) -> float:
    end = min(a.end_date or a.start_date, as_of)
    months = months_between(a.start_date, end)
    return min(p.duration_cap, 1.0 + p.duration_slope * math.log2(1.0 + months))


def level_factor(a: ActivityInput, as_of: date, p: ScoringParams = DEFAULT_PARAMS) -> float:
    return p.outcome.get(a.outcome, 1.0) * p.scope.get(a.scope, 1.0) * duration_factor(a, as_of, p)


def decay_factor(a: ActivityInput, as_of: date, p: ScoringParams = DEFAULT_PARAMS) -> float:
    """Ongoing activities (end date after as_of) do not decay."""
    end = a.end_date or a.start_date
    if end >= as_of:
        return 1.0
    return 0.5 ** (months_between(end, as_of) / p.half_life_months)


def saturate(raw: float, p: ScoringParams = DEFAULT_PARAMS) -> float:
    return 100.0 * (1.0 - math.exp(-raw / p.k))


def compute_scores(
    activities: list[ActivityInput],
    weights: dict[str, dict[str, float]],
    competency_keys: list[str],
    as_of: date,
    params: ScoringParams = DEFAULT_PARAMS,
) -> dict[str, CompetencyScore]:
    """Scores as they would have been on `as_of`: activities starting later are ignored."""
    result = {c: CompetencyScore(key=c, score=0.0, raw=0.0, contributions=[]) for c in competency_keys}
    for a in activities:
        if a.start_date > as_of:
            continue
        level = level_factor(a, as_of, params)
        conf = params.confidence.get(a.confidence_key, params.confidence["self_reported"])
        decay = decay_factor(a, as_of, params)
        for c, w in weights.get(a.type_key, {}).items():
            if w <= 0 or c not in result:
                continue
            points = w * level * conf * decay
            result[c].raw += points
            result[c].contributions.append(
                Contribution(a.id, a.title, a.type_key, a.end_date or a.start_date, w, level, conf, decay, points)
            )
    for cs in result.values():
        cs.score = saturate(cs.raw, params)
        cs.contributions.sort(key=lambda x: x.points, reverse=True)
    return result


def score_vector(scores: dict[str, CompetencyScore]) -> dict[str, float]:
    return {k: round(v.score, 2) for k, v in scores.items()}
