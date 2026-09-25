from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import cachecontrol
import google.auth.transport.requests
import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.oauth2 import id_token
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models.user import Role, User

bearer = HTTPBearer(auto_error=False)


@lru_cache
def _google_request() -> google.auth.transport.requests.Request:
    # Caches Google's public signing certs according to their Cache-Control headers.
    session = cachecontrol.CacheControl(requests.Session())
    return google.auth.transport.requests.Request(session=session)


def get_token_claims(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict[str, Any]:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        return id_token.verify_firebase_token(
            creds.credentials, _google_request(), audience=get_settings().firebase_project_id
        )
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")


def get_current_user(claims: dict[str, Any] = Depends(get_token_claims), db: Session = Depends(get_db)) -> User:
    """Return the app user for this Firebase identity, creating it on first login."""
    uid = claims["sub"]
    email = (claims.get("email") or "").lower()
    now = datetime.now(UTC)
    user = db.scalar(select(User).where(User.firebase_uid == uid))
    if user is None:
        user = User(firebase_uid=uid, email=email, name=claims.get("name") or email.split("@")[0], role=Role.learner)
        db.add(user)
        try:
            db.flush()
        except IntegrityError:
            # A concurrent first request created the user already (e.g. right after sign-up).
            db.rollback()
            user = db.scalars(select(User).where(User.firebase_uid == uid)).one()
    # Admin bootstrap only for verified emails, so nobody can self-register as admin with an unverified address.
    if claims.get("email_verified") and email in get_settings().admin_emails:
        user.role = Role.admin
    # Only write last_login_at occasionally rather than on every request.
    if user.last_login_at is None or (now - _aware(user.last_login_at)).total_seconds() > 600:
        user.last_login_at = now
    if db.dirty or db.new:
        db.commit()
    return user


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def require_consent(user: User = Depends(get_current_user)) -> User:
    if user.consent_given_at is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Consent required")
    return user


def require_roles(*roles: Role):
    def checker(user: User = Depends(require_consent)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return user

    return checker
