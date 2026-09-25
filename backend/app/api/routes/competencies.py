from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_consent
from app.core.db import get_db
from app.models import ActivityType, CompetencySnapshot, User
from app.services.competency import load_framework, learner_scores
from app.services.scoring import DEFAULT_PARAMS

router = APIRouter(tags=["competencies"])


class CompetencyDef(BaseModel):
    key: str
    label: str
    description: str | None


class ScoringConfig(BaseModel):
    competencies: list[CompetencyDef]
    activity_types: dict[str, str]  # key -> label
    weights: dict[str, dict[str, float]]
    half_life_months: float
    k: float
    confidence: dict[str, float]
    outcome: dict[str, float]
    scope: dict[str, float]


class ContributionOut(BaseModel):
    activity_id: int
    title: str
    type_key: str
    date: date
    weight: float
    level: float
    confidence: float
    decay: float
    points: float


class CompetencyScoreOut(BaseModel):
    key: str
    label: str
    score: float
    raw: float
    contributions: list[ContributionOut]


class LearnerCompetencies(BaseModel):
    as_of: date
    activity_count: int
    scores: list[CompetencyScoreOut]


class SnapshotOut(BaseModel):
    taken_at: datetime
    trigger: str
    activity_id: int | None
    scores: dict[str, float]


@router.get("/competencies/config", response_model=ScoringConfig)
def scoring_config(_: User = Depends(require_consent), db: Session = Depends(get_db)) -> ScoringConfig:
    """The full scoring model, so the UI can explain how scores are calculated."""
    fw = load_framework(db)
    types = {t.key: t.label for t in db.scalars(select(ActivityType).order_by(ActivityType.sort_order))}
    p = DEFAULT_PARAMS
    return ScoringConfig(
        competencies=[CompetencyDef(key=c.key, label=c.label, description=c.description) for c in fw.competencies],
        activity_types=types,
        weights=fw.weights,
        half_life_months=p.half_life_months,
        k=p.k,
        confidence=p.confidence,
        outcome=p.outcome,
        scope=p.scope,
    )


@router.get("/me/competencies", response_model=LearnerCompetencies)
def my_competencies(
    as_of: date | None = Query(None, description="Replay scores as of this date (default: today)"),
    user: User = Depends(require_consent),
    db: Session = Depends(get_db),
) -> LearnerCompetencies:
    day = as_of or date.today()
    if day > date.today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "as_of cannot be in the future")
    fw = load_framework(db)
    scores = learner_scores(db, user.id, day, fw)
    labels = {c.key: c.label for c in fw.competencies}
    counted = {c.activity_id for s in scores.values() for c in s.contributions}
    return LearnerCompetencies(
        as_of=day,
        activity_count=len(counted),
        scores=[
            CompetencyScoreOut(
                key=k,
                label=labels[k],
                score=round(s.score, 2),
                raw=round(s.raw, 4),
                contributions=[ContributionOut(**vars(c)) for c in s.contributions],
            )
            for k, s in scores.items()
        ],
    )


@router.get("/me/competencies/snapshots", response_model=list[SnapshotOut])
def my_snapshots(user: User = Depends(require_consent), db: Session = Depends(get_db)):
    q = select(CompetencySnapshot).where(CompetencySnapshot.user_id == user.id).order_by(CompetencySnapshot.taken_at)
    return [
        SnapshotOut(taken_at=s.taken_at, trigger=s.trigger, activity_id=s.activity_id, scores=s.scores)
        for s in db.scalars(q)
    ]
