"""Synthetic evaluation datasets, generated with the production generator into an in-memory database."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Activity, ActivityType, Base, Competency, MappingWeight, User
from app.models.seed import ACTIVITY_TYPES, COMPETENCIES, MAPPING_WEIGHTS
from app.services import synthetic
from app.services.competency import to_input
from app.services.scoring import ActivityInput

# Fixed so every run is reproducible regardless of when it is executed.
EVAL_DATE = date(2026, 9, 30)
KEYS = [c[0] for c in COMPETENCIES]
LABELS = {k: label for k, label, _ in COMPETENCIES}
TYPE_KEYS = [t[0] for t in ACTIVITY_TYPES]


@dataclass(frozen=True)
class Learner:
    id: int
    persona: str
    activities: tuple[ActivityInput, ...]


def build_dataset(seed: int, learners: int = 200, months: int = 24, end: date = EVAL_DATE) -> list[Learner]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        types = [ActivityType(key=k, label=label, description=d, sort_order=i) for i, (k, label, d) in enumerate(ACTIVITY_TYPES)]
        comps = [Competency(key=k, label=label, description=d, sort_order=i) for i, (k, label, d) in enumerate(COMPETENCIES)]
        db.add_all(types + comps)
        db.flush()
        comp_ids = {c.key: c.id for c in comps}
        db.add_all(
            MappingWeight(activity_type_id=t.id, competency_id=comp_ids[c], weight=w)
            for t in types
            for c, w in MAPPING_WEIGHTS[t.key].items()
        )
        db.commit()

        synthetic.generate(db, learners=learners, seed=seed, months=months, end=end)
        by_user: dict[int, list[ActivityInput]] = {}
        for a in db.scalars(select(Activity)):
            by_user.setdefault(a.user_id, []).append(to_input(a))
        users = db.scalars(select(User).where(User.synthetic_persona.is_not(None)).order_by(User.id)).all()
        data = [Learner(u.id, u.synthetic_persona, tuple(by_user.get(u.id, []))) for u in users]
    engine.dispose()
    return data
