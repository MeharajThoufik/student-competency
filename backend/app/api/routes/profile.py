"""Academic records, skills and interests of the signed-in learner."""

from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import require_consent
from app.core.db import get_db
from app.models import AcademicRecord, Interest, Skill, User
from app.schemas import (
    AcademicIn,
    AcademicOut,
    AcademicSummary,
    InterestIn,
    InterestOut,
    SemesterSummary,
    SkillIn,
    SkillOut,
    grade_point,
)

router = APIRouter(prefix="/me", tags=["profile"])


def _owned[T](db: Session, model: type[T], item_id: int, user: User) -> T:
    item = db.get(model, item_id)
    if item is None or item.user_id != user.id:  # type: ignore[attr-defined]
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return item


def _commit_unique(db: Session, detail: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail)


# ---------- Academics ----------
@router.get("/academics", response_model=list[AcademicOut])
def list_academics(user: User = Depends(require_consent), db: Session = Depends(get_db)):
    q = select(AcademicRecord).where(AcademicRecord.user_id == user.id)
    return db.scalars(q.order_by(AcademicRecord.semester, AcademicRecord.course_code)).all()


@router.get("/academics/summary", response_model=AcademicSummary)
def academic_summary(user: User = Depends(require_consent), db: Session = Depends(get_db)) -> AcademicSummary:
    records = db.scalars(select(AcademicRecord).where(AcademicRecord.user_id == user.id)).all()
    by_sem: dict[int, list[AcademicRecord]] = defaultdict(list)
    for r in records:
        by_sem[r.semester].append(r)

    def gpa(rs: list[AcademicRecord]) -> float:
        credits = sum(r.credits for r in rs)
        return round(sum(grade_point(r.grade) * r.credits for r in rs) / credits, 2) if credits else 0.0

    semesters = [
        SemesterSummary(semester=s, credits=sum(r.credits for r in rs), sgpa=gpa(rs)) for s, rs in sorted(by_sem.items())
    ]
    return AcademicSummary(
        semesters=semesters,
        cgpa=gpa(list(records)) if records else None,
        total_credits=sum(r.credits for r in records),
    )


@router.post("/academics", response_model=AcademicOut, status_code=201)
def create_academic(body: AcademicIn, user: User = Depends(require_consent), db: Session = Depends(get_db)):
    record = AcademicRecord(user_id=user.id, **body.model_dump())
    db.add(record)
    _commit_unique(db, "This course is already recorded for that semester")
    return record


@router.put("/academics/{record_id}", response_model=AcademicOut)
def update_academic(
    record_id: int, body: AcademicIn, user: User = Depends(require_consent), db: Session = Depends(get_db)
):
    record = _owned(db, AcademicRecord, record_id, user)
    for k, v in body.model_dump().items():
        setattr(record, k, v)
    _commit_unique(db, "This course is already recorded for that semester")
    return record


@router.delete("/academics/{record_id}", status_code=204)
def delete_academic(record_id: int, user: User = Depends(require_consent), db: Session = Depends(get_db)):
    db.delete(_owned(db, AcademicRecord, record_id, user))
    db.commit()
    return Response(status_code=204)


# ---------- Skills ----------
@router.get("/skills", response_model=list[SkillOut])
def list_skills(user: User = Depends(require_consent), db: Session = Depends(get_db)):
    return db.scalars(select(Skill).where(Skill.user_id == user.id).order_by(Skill.category, Skill.name)).all()


@router.post("/skills", response_model=SkillOut, status_code=201)
def create_skill(body: SkillIn, user: User = Depends(require_consent), db: Session = Depends(get_db)):
    skill = Skill(user_id=user.id, **body.model_dump())
    db.add(skill)
    _commit_unique(db, "Skill already added")
    return skill


@router.put("/skills/{skill_id}", response_model=SkillOut)
def update_skill(skill_id: int, body: SkillIn, user: User = Depends(require_consent), db: Session = Depends(get_db)):
    skill = _owned(db, Skill, skill_id, user)
    for k, v in body.model_dump().items():
        setattr(skill, k, v)
    _commit_unique(db, "Skill already added")
    return skill


@router.delete("/skills/{skill_id}", status_code=204)
def delete_skill(skill_id: int, user: User = Depends(require_consent), db: Session = Depends(get_db)):
    db.delete(_owned(db, Skill, skill_id, user))
    db.commit()
    return Response(status_code=204)


# ---------- Interests (soft delete keeps history for drift analysis) ----------
@router.get("/interests", response_model=list[InterestOut])
def list_interests(user: User = Depends(require_consent), db: Session = Depends(get_db)):
    q = select(Interest).where(Interest.user_id == user.id, Interest.removed_at.is_(None))
    return db.scalars(q.order_by(Interest.level.desc(), Interest.tag)).all()


@router.post("/interests", response_model=InterestOut, status_code=201)
def create_interest(body: InterestIn, user: User = Depends(require_consent), db: Session = Depends(get_db)):
    active = db.scalars(select(Interest).where(Interest.user_id == user.id, Interest.removed_at.is_(None))).all()
    if any(i.tag.lower() == body.tag.lower() for i in active):
        raise HTTPException(status.HTTP_409_CONFLICT, "Interest already added")
    interest = Interest(user_id=user.id, **body.model_dump())
    db.add(interest)
    db.commit()
    return interest


@router.delete("/interests/{interest_id}", status_code=204)
def remove_interest(interest_id: int, user: User = Depends(require_consent), db: Session = Depends(get_db)):
    interest = _owned(db, Interest, interest_id, user)
    if interest.removed_at is None:
        interest.removed_at = datetime.now(UTC)
        db.commit()
    return Response(status_code=204)
