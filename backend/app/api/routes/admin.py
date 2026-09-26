from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from scipy.stats import kendalltau
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.db import get_db
from app.models import ActivityType, AuditLog, Competency, MappingWeight, Role, User
from app.models.seed import MAPPING_WEIGHTS
from app.services import synthetic
from app.services.audit import audit
from app.services.cohort import activities_by_user, learner_query
from app.services.competency import load_framework, to_input
from app.services.scoring import compute_scores

router = APIRouter(prefix="/admin", tags=["admin"])
admin_only = require_roles(Role.admin)


# ---------- Synthetic learners ----------
class SyntheticRequest(BaseModel):
    learners: int = Field(200, ge=1, le=1000)
    seed: int = 42
    months: int = Field(24, ge=3, le=60)


class SyntheticSummary(BaseModel):
    total: int
    by_persona: dict[str, int]


def _summary(counts: dict[str, int]) -> SyntheticSummary:
    return SyntheticSummary(total=sum(counts.values()), by_persona=counts)


@router.get("/synthetic", response_model=SyntheticSummary)
def get_synthetic(_: User = Depends(admin_only), db: Session = Depends(get_db)):
    return _summary(synthetic.synthetic_summary(db))


@router.post("/synthetic", response_model=SyntheticSummary)
def seed_synthetic(body: SyntheticRequest, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    """Replace all synthetic learners with a fresh deterministic set."""
    counts = synthetic.generate(db, learners=body.learners, seed=body.seed, months=body.months)
    audit(db, admin, "synthetic_generated", "synthetic", None, **body.model_dump(), by_persona=counts)
    db.commit()
    return _summary(counts)


@router.delete("/synthetic", response_model=SyntheticSummary)
def clear_synthetic(admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    deleted = synthetic.delete_synthetic(db)
    audit(db, admin, "synthetic_deleted", "synthetic", None, deleted=deleted)
    db.commit()
    return _summary({})


# ---------- Users and roles ----------
class AdminUserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    register_no: str | None
    batch: str | None
    consent_given_at: datetime | None
    last_login_at: datetime | None


class RoleIn(BaseModel):
    role: Role


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    q: str | None = Query(None, max_length=100),
    role: Role | None = None,
    _: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    """Real accounts only (synthetic learners are managed as a set)."""
    stmt = select(User).where(User.synthetic_persona.is_(None))
    if role:
        stmt = stmt.where(User.role == role)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.name.ilike(like), User.email.ilike(like), User.register_no.ilike(like)))
    return db.scalars(stmt.order_by(User.name).limit(500)).all()


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def set_role(user_id: int, body: RoleIn, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None or user.synthetic_persona is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == admin.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "You cannot change your own role")
    if user.role != body.role:
        audit(db, admin, "role_changed", "user", user.id, email=user.email, previous=user.role, new=body.role.value)
        user.role = body.role
        db.commit()
    return user


# ---------- Weight matrix ----------
class WeightsIn(BaseModel):
    """Partial update: {activity type key: {competency key: weight 0–1}}."""

    weights: dict[str, dict[str, float]]


def _weight_rows(db: Session) -> dict[tuple[str, str], MappingWeight]:
    rows = db.execute(
        select(ActivityType.key, Competency.key, MappingWeight)
        .join(ActivityType, ActivityType.id == MappingWeight.activity_type_id)
        .join(Competency, Competency.id == MappingWeight.competency_id)
    ).all()
    return {(t, c): mw for t, c, mw in rows}


def _merge(db: Session, new: dict[str, dict[str, float]]):
    """Validate a partial update and merge it into the current matrix (nothing is written)."""
    types = dict(db.execute(select(ActivityType.key, ActivityType.id)).all())
    comps = dict(db.execute(select(Competency.key, Competency.id)).all())
    rows = _weight_rows(db)
    errors = []
    for t, ws in new.items():
        if t not in types:
            errors.append(f"Unknown activity type '{t}'")
            continue
        for c, w in ws.items():
            if c not in comps:
                errors.append(f"Unknown competency '{c}'")
            elif not 0 <= w <= 1:
                errors.append(f"{t}/{c}: weight must be between 0 and 1")
    if errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "; ".join(errors))

    current = {t: {c: (rows[(t, c)].weight if (t, c) in rows else 0.0) for c in comps} for t in types}
    merged = {t: {**current[t], **{c: round(w, 3) for c, w in new.get(t, {}).items()}} for t in types}
    empty = [t for t, ws in merged.items() if not any(w > 0 for w in ws.values())]
    if empty:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Every activity type needs a positive weight: {', '.join(empty)}")
    return types, comps, rows, current, merged


def _apply_weights(db: Session, admin: User, new: dict[str, dict[str, float]], action: str) -> dict[str, dict[str, float]]:
    types, comps, rows, current, merged = _merge(db, new)
    changes: dict[str, dict[str, list[float]]] = {}
    for t, ws in merged.items():
        for c, w in ws.items():
            if w == current[t][c]:
                continue
            changes.setdefault(t, {})[c] = [current[t][c], w]
            if (t, c) in rows:
                rows[(t, c)].weight = w
            else:
                db.add(MappingWeight(activity_type_id=types[t], competency_id=comps[c], weight=w))
    if changes:
        audit(db, admin, action, "mapping_weights", None, changes=changes)
        db.commit()
    return merged


@router.put("/weights", response_model=dict[str, dict[str, float]])
def update_weights(body: WeightsIn, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    """Scores are computed on read, so every learner's scores update immediately. Past snapshots are kept as recorded."""
    return _apply_weights(db, admin, body.weights, "weights_updated")


class CompetencyImpact(BaseModel):
    key: str
    label: str
    kendall_tau: float | None  # rank agreement of learners, current vs draft (1 = same order)
    mean_change: float
    max_abs_change: float


class WeightImpact(BaseModel):
    learners: int
    changed_weights: int
    mean_kendall_tau: float | None
    top_changed: int  # learners whose strongest competency would change
    competencies: list[CompetencyImpact]


@router.post("/weights/preview", response_model=WeightImpact)
def preview_weights(body: WeightsIn, _: User = Depends(admin_only), db: Session = Depends(get_db)) -> WeightImpact:
    """What a weight change would do to every learner's current scores, without saving it."""
    _, _, _, current, merged = _merge(db, body.weights)
    changed = sum(merged[t][c] != current[t][c] for t in merged for c in merged[t])
    fw = load_framework(db)
    today = date.today()
    users = list(db.scalars(learner_query(synthetic="include")))
    histories = [[to_input(a) for a in acts] for acts in activities_by_user(db, users).values() if acts]

    before = [compute_scores(h, current, fw.keys, today) for h in histories]
    after = [compute_scores(h, merged, fw.keys, today) for h in histories]
    items, taus = [], []
    for c in fw.competencies:
        a = [s[c.key].score for s in before]
        b = [s[c.key].score for s in after]
        diffs = [y - x for x, y in zip(a, b, strict=True)]
        tau = kendalltau(a, b).statistic if len(a) > 1 else float("nan")
        tau = None if tau != tau else round(float(tau), 4)  # NaN when scores are constant
        if tau is not None:
            taus.append(tau)
        items.append(
            CompetencyImpact(
                key=c.key,
                label=c.label,
                kendall_tau=tau,
                mean_change=round(sum(diffs) / len(diffs), 2) if diffs else 0.0,
                max_abs_change=round(max((abs(d) for d in diffs), default=0.0), 2),
            )
        )
    top = lambda s: max(fw.keys, key=lambda k: s[k].score)  # noqa: E731
    return WeightImpact(
        learners=len(histories),
        changed_weights=changed,
        mean_kendall_tau=round(sum(taus) / len(taus), 4) if taus else None,
        top_changed=sum(top(x) != top(y) for x, y in zip(before, after, strict=True)),
        competencies=items,
    )


@router.post("/weights/reset", response_model=dict[str, dict[str, float]])
def reset_weights(admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    return _apply_weights(db, admin, MAPPING_WEIGHTS, "weights_reset")


# ---------- Audit log ----------
class AuditOut(BaseModel):
    id: int
    created_at: datetime
    actor: str | None
    action: str
    target_type: str
    target_id: int | None
    details: dict[str, Any]


@router.get("/audit", response_model=list[AuditOut])
def audit_log(
    limit: int = Query(100, ge=1, le=500),
    action: str | None = None,
    _: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    stmt = select(AuditLog, User.email).outerjoin(User, User.id == AuditLog.actor_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    rows = db.execute(stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)).all()
    return [
        AuditOut(
            id=a.id, created_at=a.created_at, actor=email, action=a.action,
            target_type=a.target_type, target_id=a.target_id, details=a.details,
        )  # fmt: skip
        for a, email in rows
    ]
