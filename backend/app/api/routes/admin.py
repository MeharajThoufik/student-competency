from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.db import get_db
from app.models import Role, User
from app.services import synthetic

router = APIRouter(prefix="/admin", tags=["admin"])
admin_only = require_roles(Role.admin)


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
def seed_synthetic(body: SyntheticRequest, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    """Replace all synthetic learners with a fresh deterministic set."""
    return _summary(synthetic.generate(db, learners=body.learners, seed=body.seed, months=body.months))


@router.delete("/synthetic", response_model=SyntheticSummary)
def clear_synthetic(_: User = Depends(admin_only), db: Session = Depends(get_db)):
    synthetic.delete_synthetic(db)
    return _summary({})
