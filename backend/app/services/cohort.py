"""Per-learner summaries and cohort statistics for educators."""

import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Activity, Role, User
from app.services import analytics
from app.services.competency import Framework, to_input

SyntheticFilter = Literal["exclude", "include", "only"]

# Explainable at-risk rules (shown to educators verbatim).
RISK_RULES: dict[str, str] = {
    "no_activity": "No activities recorded yet",
    "inactive": f"No new activity in the last {analytics.DEFAULT_TREND.window_months} months",
    "declining": f"Two or more competencies declining over the last {analytics.DEFAULT_TREND.window_months} months",
}


@dataclass
class LearnerRow:
    user: User
    activity_count: int
    last_activity: date | None
    pending_reviews: int
    scores: dict[str, float]
    trends: dict[str, str]
    mean_score: float
    top_competency: str | None
    risks: list[str]
    evidence: Counter  # confidence key -> activity count
    type_counts: Counter  # activity type key -> count


def learner_query(q: str | None = None, batch: str | None = None, synthetic: SyntheticFilter = "exclude"):
    stmt = select(User).where(User.role == Role.learner, User.consent_given_at.is_not(None))
    if synthetic == "exclude":
        stmt = stmt.where(User.synthetic_persona.is_(None))
    elif synthetic == "only":
        stmt = stmt.where(User.synthetic_persona.is_not(None))
    if batch:
        stmt = stmt.where(User.batch == batch)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.name.ilike(like), User.email.ilike(like), User.register_no.ilike(like)))
    return stmt.order_by(User.name)


def learner_rows(db: Session, fw: Framework, today: date, users: list[User]) -> list[LearnerRow]:
    by_user: dict[int, list[Activity]] = defaultdict(list)
    ids = [u.id for u in users]
    for chunk in (ids[i : i + 500] for i in range(0, len(ids), 500)):
        for a in db.scalars(select(Activity).where(Activity.user_id.in_(chunk))):
            by_user[a.user_id].append(a)

    window = analytics.DEFAULT_TREND.window_months
    cutoff = analytics.add_months(today, -window)
    rows = []
    for u in users:
        acts = by_user.get(u.id, [])
        inputs = [to_input(a) for a in acts]
        series = analytics.monthly_series(inputs, fw.weights, fw.keys, today, max_months=window)
        tr = analytics.trends(series)
        scores = {k: t.score for k, t in tr.items()}
        labels = {k: t.label for k, t in tr.items()}
        last = max((a.start_date for a in acts), default=None)

        risks = []
        if not acts:
            risks.append("no_activity")
        elif last is not None and last < cutoff:
            risks.append("inactive")
        if sum(label == "declining" for label in labels.values()) >= 2:
            risks.append("declining")

        rows.append(
            LearnerRow(
                user=u,
                activity_count=len(acts),
                last_activity=last,
                pending_reviews=sum(a.verification_status == "unverified" and bool(a.evidence) for a in acts),
                scores=scores,
                trends=labels,
                mean_score=round(statistics.fmean(scores.values()), 2) if scores else 0.0,
                top_competency=max(scores, key=lambda k: scores[k]) if acts else None,
                risks=risks,
                evidence=Counter(i.confidence_key for i in inputs),
                type_counts=Counter(i.type_key for i in inputs),
            )
        )
    return rows


@dataclass
class Distribution:
    mean: float
    minimum: float
    p25: float
    median: float
    p75: float
    maximum: float


def distribution(values: list[float]) -> Distribution | None:
    if not values:
        return None
    if len(values) == 1:
        v = values[0]
        return Distribution(v, v, v, v, v, v)
    q1, q2, q3 = statistics.quantiles(values, n=4, method="inclusive")
    r = lambda x: round(x, 2)  # noqa: E731
    return Distribution(r(statistics.fmean(values)), r(min(values)), r(q1), r(q2), r(q3), r(max(values)))
