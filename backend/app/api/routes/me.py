from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models import User
from app.schemas import UserOut, UserUpdate

router = APIRouter(prefix="/me", tags=["profile"])


@router.get("", response_model=UserOut)
def read_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("", response_model=UserOut)
def update_me(body: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    return user


@router.post("/consent", response_model=UserOut)
def give_consent(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if user.consent_given_at is None:
        user.consent_given_at = datetime.now(UTC)
        db.commit()
    return user
