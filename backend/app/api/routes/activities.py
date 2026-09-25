import hashlib
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_consent
from app.core.config import get_settings
from app.core.db import get_db
from app.models import Activity, ActivityType, EvidenceFile, Role, User
from app.schemas import ActivityIn, ActivityOut, ActivityTypeOut, EvidenceOut
from app.services.storage import get_storage

router = APIRouter(tags=["activities"])

MAX_EVIDENCE_PER_ACTIVITY = 5

# Detect file type from content, not the client-supplied header.
_SIGNATURES: list[tuple[bytes, str, str]] = [
    (b"%PDF-", "application/pdf", "pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
]


def _sniff(data: bytes) -> tuple[str, str] | None:
    for sig, mime, ext in _SIGNATURES:
        if data.startswith(sig):
            return mime, ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


@router.get("/activity-types", response_model=list[ActivityTypeOut])
def list_activity_types(_: User = Depends(require_consent), db: Session = Depends(get_db)):
    return db.scalars(select(ActivityType).order_by(ActivityType.sort_order)).all()


def _own_activity(db: Session, activity_id: int, user: User) -> Activity:
    activity = db.get(Activity, activity_id)
    if activity is None or activity.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found")
    return activity


def _apply(activity: Activity, body: ActivityIn, db: Session) -> None:
    if db.get(ActivityType, body.type_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown activity type")
    data = body.model_dump()
    data["url"] = str(body.url) if body.url else None
    for k, v in data.items():
        setattr(activity, k, v)


@router.get("/me/activities", response_model=list[ActivityOut])
def list_activities(user: User = Depends(require_consent), db: Session = Depends(get_db)):
    q = select(Activity).where(Activity.user_id == user.id).order_by(Activity.start_date.desc(), Activity.id.desc())
    return db.scalars(q).all()


@router.post("/me/activities", response_model=ActivityOut, status_code=201)
def create_activity(body: ActivityIn, user: User = Depends(require_consent), db: Session = Depends(get_db)):
    activity = Activity(user_id=user.id)
    _apply(activity, body, db)
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


@router.get("/me/activities/{activity_id}", response_model=ActivityOut)
def get_activity(activity_id: int, user: User = Depends(require_consent), db: Session = Depends(get_db)):
    return _own_activity(db, activity_id, user)


@router.put("/me/activities/{activity_id}", response_model=ActivityOut)
def update_activity(
    activity_id: int, body: ActivityIn, user: User = Depends(require_consent), db: Session = Depends(get_db)
):
    activity = _own_activity(db, activity_id, user)
    _apply(activity, body, db)
    # Editing a verified claim invalidates the verification.
    if activity.verification_status == "verified":
        activity.verification_status = "unverified"
        activity.verified_by = None
        activity.verified_at = None
    db.commit()
    db.refresh(activity)
    return activity


@router.delete("/me/activities/{activity_id}", status_code=204)
def delete_activity(activity_id: int, user: User = Depends(require_consent), db: Session = Depends(get_db)):
    activity = _own_activity(db, activity_id, user)
    keys = [e.storage_key for e in activity.evidence]
    db.delete(activity)
    db.commit()
    storage = get_storage()
    for key in keys:
        storage.delete(key)
    return Response(status_code=204)


# ---------- Evidence ----------
@router.post("/me/activities/{activity_id}/evidence", response_model=EvidenceOut, status_code=201)
async def upload_evidence(
    activity_id: int, file: UploadFile, user: User = Depends(require_consent), db: Session = Depends(get_db)
):
    activity = _own_activity(db, activity_id, user)
    if len(activity.evidence) >= MAX_EVIDENCE_PER_ACTIVITY:
        raise HTTPException(status.HTTP_409_CONFLICT, f"At most {MAX_EVIDENCE_PER_ACTIVITY} files per activity")

    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"File exceeds {get_settings().max_upload_mb} MB")
    kind = _sniff(data)
    if kind is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only PDF, PNG, JPEG or WEBP files are allowed")
    mime, ext = kind

    key = f"evidence/{user.id}/{activity.id}/{uuid.uuid4().hex}.{ext}"
    get_storage().save(key, data, mime)
    evidence = EvidenceFile(
        activity_id=activity.id,
        storage_key=key,
        filename=(file.filename or f"evidence.{ext}")[:255],
        content_type=mime,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )
    db.add(evidence)
    db.commit()
    return evidence


def _readable_evidence(db: Session, evidence_id: int, user: User) -> EvidenceFile:
    evidence = db.get(EvidenceFile, evidence_id)
    if evidence is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    if evidence.activity.user_id != user.id and user.role not in (Role.educator, Role.admin):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    return evidence


@router.get("/evidence/{evidence_id}/file")
def download_evidence(evidence_id: int, user: User = Depends(require_consent), db: Session = Depends(get_db)):
    evidence = _readable_evidence(db, evidence_id, user)
    data = get_storage().load(evidence.storage_key)
    # ASCII fallback plus RFC 5987 UTF-8 name, since headers must be latin-1.
    ascii_name = evidence.filename.encode("ascii", "replace").decode().replace('"', "").replace("?", "_")
    return Response(
        content=data,
        media_type=evidence.content_type,
        headers={
            "Content-Disposition": f"inline; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(evidence.filename)}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/evidence/{evidence_id}", status_code=204)
def delete_evidence(evidence_id: int, user: User = Depends(require_consent), db: Session = Depends(get_db)):
    evidence = db.get(EvidenceFile, evidence_id)
    if evidence is None or evidence.activity.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    activity = evidence.activity
    key = evidence.storage_key
    db.delete(evidence)
    # Removing proof from a verified claim invalidates the verification.
    if activity.verification_status == "verified":
        activity.verification_status = "unverified"
        activity.verified_by = None
        activity.verified_at = None
    db.commit()
    get_storage().delete(key)
    return Response(status_code=204)
