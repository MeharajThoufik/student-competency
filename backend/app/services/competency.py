"""Bridges the database and the pure scoring engine."""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, ActivityType, Competency, CompetencySnapshot, MappingWeight
from app.services.scoring import DEFAULT_PARAMS, ActivityInput, CompetencyScore, compute_scores, score_vector


@dataclass
class Framework:
    """Competency definitions + weight matrix, loaded once per request."""

    competencies: list[Competency]
    weights: dict[str, dict[str, float]]

    @property
    def keys(self) -> list[str]:
        return [c.key for c in self.competencies]


def load_framework(db: Session) -> Framework:
    competencies = list(db.scalars(select(Competency).order_by(Competency.sort_order)))
    rows = db.execute(
        select(ActivityType.key, Competency.key, MappingWeight.weight)
        .join(ActivityType, ActivityType.id == MappingWeight.activity_type_id)
        .join(Competency, Competency.id == MappingWeight.competency_id)
    )
    weights: dict[str, dict[str, float]] = {}
    for type_key, comp_key, w in rows:
        weights.setdefault(type_key, {})[comp_key] = w
    return Framework(competencies, weights)


def confidence_key(a: Activity) -> str:
    return "rejected" if a.verification_status == "rejected" else a.evidence_status


def to_input(a: Activity) -> ActivityInput:
    return ActivityInput(
        id=a.id,
        title=a.title,
        type_key=a.type.key,
        start_date=a.start_date,
        end_date=a.end_date,
        outcome=a.outcome,
        scope=a.scope,
        confidence_key=confidence_key(a),
    )


def learner_inputs(db: Session, user_id: int) -> list[ActivityInput]:
    return [to_input(a) for a in db.scalars(select(Activity).where(Activity.user_id == user_id))]


def learner_scores(
    db: Session, user_id: int, as_of: date | None = None, framework: Framework | None = None
) -> dict[str, CompetencyScore]:
    fw = framework or load_framework(db)
    return compute_scores(learner_inputs(db, user_id), fw.weights, fw.keys, as_of or date.today(), DEFAULT_PARAMS)


def record_snapshot(db: Session, user_id: int, trigger: str, activity_id: int | None = None) -> CompetencySnapshot:
    """Append the learner's current competency vector. Call after the triggering change is committed."""
    # Sessions keep objects after commit (expire_on_commit=False); reload so relationships such as
    # Activity.evidence reflect the change that triggered this snapshot.
    db.expire_all()
    snapshot = CompetencySnapshot(
        user_id=user_id,
        taken_at=datetime.now(UTC),
        scores=score_vector(learner_scores(db, user_id)),
        trigger=trigger,
        activity_id=activity_id,
    )
    db.add(snapshot)
    db.commit()
    return snapshot
