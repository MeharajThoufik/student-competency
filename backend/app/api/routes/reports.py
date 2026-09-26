"""PDF competency reports: learners download their own, educators any learner's."""

import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.insights import build_insights
from app.api.routes.profile import academic_summary_for
from app.core.auth import require_consent, require_roles
from app.core.db import get_db
from app.models import Activity, Role, User
from app.schemas import ActivityOut, UserOut
from app.services.report_pdf import build_report

router = APIRouter(tags=["reports"])


def _pdf(db: Session, learner: User, generated_by: str | None) -> Response:
    activities = db.scalars(
        select(Activity).where(Activity.user_id == learner.id).order_by(Activity.start_date.desc(), Activity.id.desc())
    ).all()
    data = build_report(
        UserOut.model_validate(learner),
        build_insights(db, learner.id),
        academic_summary_for(db, learner.id),
        [ActivityOut.model_validate(a) for a in activities],
        generated_by=generated_by,
    )
    slug = re.sub(r"[^A-Za-z0-9]+", "-", learner.register_no or learner.name).strip("-") or "learner"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="competency-report-{slug}-{date.today()}.pdf"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/me/report.pdf")
def my_report(user: User = Depends(require_consent), db: Session = Depends(get_db)) -> Response:
    return _pdf(db, user, None)


@router.get("/educator/learners/{user_id}/report.pdf")
def learner_report(
    user_id: int, staff: User = Depends(require_roles(Role.educator, Role.admin)), db: Session = Depends(get_db)
) -> Response:
    learner = db.get(User, user_id)
    if learner is None or learner.role != Role.learner or learner.consent_given_at is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Learner not found")
    return _pdf(db, learner, staff.name)
