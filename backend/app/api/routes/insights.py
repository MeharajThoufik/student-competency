from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_consent
from app.core.db import get_db
from app.models import ActivityType, Interest, User
from app.services import analytics
from app.services.competency import cohort_scores, learner_inputs, load_framework

router = APIRouter(tags=["insights"])


class CompetencyTrendOut(BaseModel):
    key: str
    label: str
    score: float
    previous: float  # score at the start of the trend window
    change: float
    slope: float  # points per month over the window
    trend: str  # emerging | improving | stable | declining | inactive
    percentile: float | None  # vs other learners


class SeriesOut(BaseModel):
    dates: list[date]
    scores: dict[str, list[float]]


class RecommendationOut(BaseModel):
    kind: str
    competency: str | None
    title: str
    detail: str
    gain: float
    activity_types: list[str]
    activity_ids: list[int]


class TimelineEntryOut(BaseModel):
    activity_id: int
    title: str
    type_key: str
    start_date: date
    end_date: date | None
    evidence_status: str
    deltas: dict[str, float]


class InterestHistoryOut(BaseModel):
    tag: str
    level: int
    added: datetime
    removed: datetime | None


class InterestDriftOut(BaseModel):
    since: datetime | None
    then: list[str]
    now: list[str]
    added: list[str]
    removed: list[str]
    drift: float | None
    history: list[InterestHistoryOut]


class InsightsOut(BaseModel):
    as_of: date
    window_months: int
    activity_count: int
    cohort_size: int
    series: SeriesOut
    competencies: list[CompetencyTrendOut]
    strengths: list[str]
    gaps: list[str]
    recommendations: list[RecommendationOut]
    timeline: list[TimelineEntryOut]
    interests: InterestDriftOut


@router.get("/me/insights", response_model=InsightsOut)
def my_insights(user: User = Depends(require_consent), db: Session = Depends(get_db)) -> InsightsOut:
    return build_insights(db, user.id)


def build_insights(db: Session, user_id: int) -> InsightsOut:
    today = date.today()
    fw = load_framework(db)
    keys, labels = fw.keys, {c.key: c.label for c in fw.competencies}
    type_labels = dict(db.execute(select(ActivityType.key, ActivityType.label)).all())
    activities = learner_inputs(db, user_id)

    series = analytics.monthly_series(activities, fw.weights, keys, today)
    trend_by_key = analytics.trends(series)
    current = {k: t.score for k, t in trend_by_key.items()}
    strengths, gaps = analytics.strengths_and_gaps(current) if activities else ([], [])
    cohort = cohort_scores(db, user_id, today, fw)

    interests = db.scalars(select(Interest).where(Interest.user_id == user_id).order_by(Interest.created_at)).all()
    records = [analytics.InterestRecord(i.tag, i.level, _utc(i.created_at), _utc(i.removed_at)) for i in interests]
    drift = analytics.interest_drift(records, datetime.now(UTC))

    return InsightsOut(
        as_of=today,
        window_months=analytics.DEFAULT_TREND.window_months,
        activity_count=len(activities),
        cohort_size=len(cohort),
        series=SeriesOut(dates=series.dates, scores=series.scores),
        competencies=[
            CompetencyTrendOut(
                key=k,
                label=labels[k],
                score=t.score,
                previous=t.previous,
                change=t.change,
                slope=t.slope,
                trend=t.label,
                percentile=analytics.percentile(t.score, [c[k] for c in cohort]) if activities else None,
            )
            for k, t in trend_by_key.items()
        ],
        strengths=strengths,
        gaps=gaps,
        recommendations=[
            RecommendationOut(**vars(r))
            for r in analytics.recommendations(activities, fw.weights, keys, labels, type_labels, trend_by_key, gaps, today)
        ],
        timeline=[
            TimelineEntryOut(
                activity_id=e.activity_id,
                title=e.title,
                type_key=e.type_key,
                start_date=e.start_date,
                end_date=e.end_date,
                evidence_status=e.confidence_key,
                deltas=e.deltas,
            )
            for e in analytics.timeline(activities, fw.weights, keys, today)
        ],
        interests=InterestDriftOut(
            **vars(drift),
            history=[InterestHistoryOut(tag=r.tag, level=r.level, added=r.created_at, removed=r.removed_at) for r in records],
        ),
    )


def _utc(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; treat them as UTC."""
    return dt.replace(tzinfo=UTC) if dt is not None and dt.tzinfo is None else dt
