"""Educator views: evidence review queue, learner list/detail and cohort analytics."""

from collections import Counter
from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes.insights import InsightsOut, build_insights
from app.api.routes.profile import academic_summary_for
from app.core.auth import require_roles
from app.core.db import get_db
from app.models import Activity, ActivityType, Interest, Role, Skill, User
from app.schemas import AcademicSummary, ActivityOut, InterestOut, SkillOut, UserOut
from app.services import analytics, clustering
from app.services.audit import audit
from app.services.cohort import RISK_RULES, SyntheticFilter, activities_by_user, distribution, learner_query, learner_rows
from app.services.competency import load_framework, record_snapshot, to_input

router = APIRouter(prefix="/educator", tags=["educator"])
staff = require_roles(Role.educator, Role.admin)


class LearnerRef(BaseModel):
    id: int
    name: str
    email: str
    register_no: str | None
    batch: str | None
    synthetic: bool


def _ref(u: User) -> LearnerRef:
    return LearnerRef(
        id=u.id, name=u.name, email=u.email, register_no=u.register_no, batch=u.batch, synthetic=u.synthetic_persona is not None
    )


# ---------- Review queue ----------
ReviewStatus = Literal["pending", "verified", "rejected"]


class ReviewItem(BaseModel):
    learner: LearnerRef
    activity: ActivityOut


class ReviewQueue(BaseModel):
    total: int
    items: list[ReviewItem]


class ReviewIn(BaseModel):
    decision: Literal["verify", "reject"]
    note: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def _reject_needs_note(self):
        self.note = (self.note or "").strip() or None
        if self.decision == "reject" and not self.note:
            raise ValueError("A note is required when rejecting, so the learner knows what to fix")
        return self


@router.get("/queue", response_model=ReviewQueue)
def review_queue(
    status_: ReviewStatus = Query("pending", alias="status"),
    synthetic: SyntheticFilter = "exclude",
    limit: int = Query(50, ge=1, le=200),
    _: User = Depends(staff),
    db: Session = Depends(get_db),
) -> ReviewQueue:
    """Pending = unverified activities that have evidence attached (oldest first)."""
    stmt = select(Activity, User).join(User, User.id == Activity.user_id).where(User.role == Role.learner)
    if synthetic == "exclude":
        stmt = stmt.where(User.synthetic_persona.is_(None))
    elif synthetic == "only":
        stmt = stmt.where(User.synthetic_persona.is_not(None))
    if status_ == "pending":
        stmt = stmt.where(Activity.verification_status == "unverified", Activity.evidence.any())
        order = Activity.updated_at.asc()
    else:
        stmt = stmt.where(Activity.verification_status == ("verified" if status_ == "verified" else "rejected"))
        order = Activity.verified_at.desc()
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.order_by(order, Activity.id).limit(limit)).unique().all()
    return ReviewQueue(total=total, items=[ReviewItem(learner=_ref(u), activity=ActivityOut.model_validate(a)) for a, u in rows])


@router.post("/activities/{activity_id}/review", response_model=ActivityOut)
def review_activity(activity_id: int, body: ReviewIn, reviewer: User = Depends(staff), db: Session = Depends(get_db)):
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found")
    if activity.user_id == reviewer.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot review your own activity")
    previous = activity.verification_status
    activity.verification_status = "verified" if body.decision == "verify" else "rejected"
    activity.verified_by = reviewer.id
    activity.verified_at = datetime.now(UTC)
    activity.review_note = body.note
    audit(
        db, reviewer, f"activity_{activity.verification_status}", "activity", activity.id,
        learner_id=activity.user_id, previous=previous, note=body.note,
    )  # fmt: skip
    db.commit()
    record_snapshot(db, activity.user_id, f"activity_{activity.verification_status}", activity.id)
    db.refresh(activity)
    return activity


# ---------- Learners ----------
class LearnerSummary(BaseModel):
    learner: LearnerRef
    activity_count: int
    last_activity: date | None
    pending_reviews: int
    mean_score: float
    top_competency: str | None
    scores: dict[str, float]
    trends: dict[str, str]
    risks: list[str]


class LearnerList(BaseModel):
    total: int
    items: list[LearnerSummary]
    risk_rules: dict[str, str]


@router.get("/learners", response_model=LearnerList)
def list_learners(
    q: str | None = Query(None, max_length=100),
    batch: str | None = None,
    synthetic: SyntheticFilter = "exclude",
    at_risk: bool = False,
    sort: Literal["name", "mean_score", "activity_count", "last_activity", "pending_reviews"] = "name",
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: User = Depends(staff),
    db: Session = Depends(get_db),
) -> LearnerList:
    fw = load_framework(db)
    users = list(db.scalars(learner_query(q, batch, synthetic)))
    rows = learner_rows(db, fw, date.today(), users)
    if at_risk:
        rows = [r for r in rows if r.risks]
    sort_keys = {
        "mean_score": lambda r: r.mean_score,
        "activity_count": lambda r: r.activity_count,
        "pending_reviews": lambda r: r.pending_reviews,
        "last_activity": lambda r: r.last_activity or date.min,  # never-active last
    }
    if sort in sort_keys:
        rows.sort(key=sort_keys[sort], reverse=True)  # highest / most recent first
    page = rows[offset : offset + limit]
    return LearnerList(
        total=len(rows),
        risk_rules=RISK_RULES,
        items=[
            LearnerSummary(
                learner=_ref(r.user),
                activity_count=r.activity_count,
                last_activity=r.last_activity,
                pending_reviews=r.pending_reviews,
                mean_score=r.mean_score,
                top_competency=r.top_competency,
                scores=r.scores,
                trends=r.trends,
                risks=r.risks,
            )
            for r in page
        ],
    )


class LearnerProfileOut(UserOut):
    synthetic: bool


class LearnerDetail(BaseModel):
    profile: LearnerProfileOut
    academics: AcademicSummary
    skills: list[SkillOut]
    interests: list[InterestOut]
    activities: list[ActivityOut]
    insights: InsightsOut
    risks: list[str]
    risk_rules: dict[str, str]


@router.get("/learners/{user_id}", response_model=LearnerDetail)
def learner_detail(user_id: int, _: User = Depends(staff), db: Session = Depends(get_db)) -> LearnerDetail:
    learner = db.get(User, user_id)
    if learner is None or learner.role != Role.learner or learner.consent_given_at is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Learner not found")
    row = learner_rows(db, load_framework(db), date.today(), [learner])[0]
    return LearnerDetail(
        profile=LearnerProfileOut(**UserOut.model_validate(learner).model_dump(), synthetic=learner.synthetic_persona is not None),
        academics=academic_summary_for(db, user_id),
        skills=db.scalars(select(Skill).where(Skill.user_id == user_id).order_by(Skill.category, Skill.name)).all(),
        interests=db.scalars(
            select(Interest).where(Interest.user_id == user_id, Interest.removed_at.is_(None)).order_by(Interest.tag)
        ).all(),
        activities=db.scalars(
            select(Activity).where(Activity.user_id == user_id).order_by(Activity.start_date.desc(), Activity.id.desc())
        ).all(),
        insights=build_insights(db, user_id),
        risks=row.risks,
        risk_rules=RISK_RULES,
    )


# ---------- Cohort ----------
class DistributionOut(BaseModel):
    key: str
    label: str
    mean: float
    minimum: float
    p25: float
    median: float
    p75: float
    maximum: float
    trends: dict[str, int]  # trend label -> learners


class CountOut(BaseModel):
    key: str
    label: str
    count: int


class CohortOut(BaseModel):
    as_of: date
    learner_count: int
    active_count: int  # at least one activity in the trend window
    window_months: int
    competencies: list[DistributionOut]
    risk_counts: dict[str, int]
    risk_rules: dict[str, str]
    evidence: dict[str, int]
    activity_types: list[CountOut]
    batches: list[str]


@router.get("/cohort", response_model=CohortOut)
def cohort(
    batch: str | None = None,
    synthetic: SyntheticFilter = "include",
    _: User = Depends(staff),
    db: Session = Depends(get_db),
) -> CohortOut:
    today = date.today()
    fw = load_framework(db)
    rows = learner_rows(db, fw, today, list(db.scalars(learner_query(None, batch, synthetic))))
    with_activity = [r for r in rows if r.activity_count]
    type_labels = dict(db.execute(select(ActivityType.key, ActivityType.label)).all())
    types: Counter = sum((r.type_counts for r in rows), Counter())
    evidence: Counter = sum((r.evidence for r in rows), Counter())
    batch_stmt = select(User.batch).where(User.role == Role.learner, User.batch.is_not(None)).distinct()
    if synthetic == "exclude":
        batch_stmt = batch_stmt.where(User.synthetic_persona.is_(None))

    competencies = []
    for c in fw.competencies:
        d = distribution([r.scores[c.key] for r in with_activity])
        if d is None:
            continue
        counts = Counter(r.trends[c.key] for r in with_activity)
        competencies.append(
            DistributionOut(key=c.key, label=c.label, **vars(d), trends={t: counts.get(t, 0) for t in analytics.TREND_LABELS})
        )
    cutoff = analytics.add_months(today, -analytics.DEFAULT_TREND.window_months)
    return CohortOut(
        as_of=today,
        learner_count=len(rows),
        active_count=sum(1 for r in rows if r.last_activity and r.last_activity >= cutoff),
        window_months=analytics.DEFAULT_TREND.window_months,
        competencies=competencies,
        risk_counts={k: sum(k in r.risks for r in rows) for k in RISK_RULES},
        risk_rules=RISK_RULES,
        evidence={k: evidence.get(k, 0) for k in ("self_reported", "evidence_attached", "verified", "rejected")},
        activity_types=[CountOut(key=k, label=type_labels.get(k, k), count=n) for k, n in types.most_common()],
        batches=sorted(b for b in db.scalars(batch_stmt) if b),
    )


# ---------- Learner groups (P5) ----------
class KChoiceOut(BaseModel):
    k: int
    silhouette: float
    davies_bouldin: float
    inertia: float


class AlgorithmOut(BaseModel):
    name: str
    n_clusters: int
    noise: float
    silhouette: float | None
    davies_bouldin: float | None
    ari: float | None
    nmi: float | None


class GroupOut(BaseModel):
    id: int
    name: str
    description: str
    size: int
    defining: list[str]
    mean_scores: dict[str, float]
    lift: dict[str, float]


class GroupMember(BaseModel):
    learner: LearnerRef
    states: list[int]  # group id per period, -1 = not active yet
    position: tuple[float, float] | None  # PCA, current period


class TransitionCount(BaseModel):
    source: int
    target: int
    learners: int


class PersonaAgreement(BaseModel):
    ari: float
    nmi: float
    contingency: dict[str, dict[str, int]]


class GroupingOut(BaseModel):
    as_of: date
    period_dates: list[date]
    features: str
    k: int
    k_selection: list[KChoiceOut]
    algorithms: list[AlgorithmOut]
    groups: list[GroupOut]
    members: list[GroupMember]
    pca_explained: list[float]
    transitions: list[list[TransitionCount]]  # one list per consecutive period pair
    movement_rate: float | None
    persona_agreement: PersonaAgreement | None
    notes: list[str]


@router.get("/groups", response_model=GroupingOut)
def learner_groups(
    batch: str | None = None,
    synthetic: SyntheticFilter = "include",
    k: int | None = Query(None, ge=2, le=8, description="Number of groups; omit to choose by silhouette"),
    _: User = Depends(staff),
    db: Session = Depends(get_db),
) -> GroupingOut:
    fw = load_framework(db)
    users = list(db.scalars(learner_query(None, batch, synthetic)))
    acts = activities_by_user(db, users)
    histories = [
        clustering.LearnerHistory(u.id, tuple(to_input(a) for a in acts.get(u.id, [])), u.synthetic_persona) for u in users
    ]
    labels = {c.key: c.label for c in fw.competencies}
    try:
        g = clustering.group_learners(histories, fw.weights, fw.keys, labels, date.today(), k=k)
    except clustering.NotEnoughLearners as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e

    return GroupingOut(
        as_of=g.as_of,
        period_dates=g.period_dates,
        features="Competency profile shape (share of points per competency) + activity volume",
        k=g.k,
        k_selection=[KChoiceOut(**vars(c)) for c in g.k_selection],
        algorithms=[AlgorithmOut(**vars(a)) for a in g.algorithms],
        groups=[GroupOut(**vars(gr)) for gr in g.groups],
        members=[GroupMember(learner=_ref(u), states=g.assignments[u.id], position=g.pca.get(u.id)) for u in users],
        pca_explained=g.pca_explained,
        transitions=[
            [TransitionCount(source=a, target=b, learners=n) for (a, b), n in sorted(t.items())] for t in g.transitions
        ],
        movement_rate=g.movement_rate,
        persona_agreement=PersonaAgreement(**g.persona_agreement) if g.persona_agreement else None,
        notes=g.notes,
    )
