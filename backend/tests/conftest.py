"""Test setup.

Uses TEST_DATABASE_URL (Postgres in CI) when set, otherwise in-memory SQLite.
Firebase token verification is replaced: the `X-Test-User` header names the caller,
e.g. "alice" or "alice;admin@x.com;verified".
"""

import os
from collections.abc import Iterator

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import activities as activities_routes
from app.core.auth import get_token_claims
from app.core.config import get_settings
from app.core.db import get_db
from app.main import app
from app.models import ActivityType, Base
from app.models.seed import ACTIVITY_TYPES
from app.services.storage import LocalStorage

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture
def engine():
    if TEST_DB_URL:
        eng = create_engine(TEST_DB_URL)
    else:
        eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add_all(
            ActivityType(key=k, label=label, description=d, sort_order=i) for i, (k, label, d) in enumerate(ACTIVITY_TYPES)
        )
        s.commit()
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


def fake_claims(x_test_user: str | None = Header(None)) -> dict:
    if not x_test_user:
        raise HTTPException(401, "Missing bearer token")
    name, _, rest = x_test_user.partition(";")
    email, _, verified = rest.partition(";")
    return {"sub": f"uid-{name}", "email": email or f"{name}@example.com", "name": name, "email_verified": verified == "verified"}


@pytest.fixture
def client(engine, tmp_path, monkeypatch) -> Iterator[TestClient]:
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_token_claims] = fake_claims
    monkeypatch.setattr(activities_routes, "get_storage", lambda: LocalStorage(str(tmp_path / "uploads")))
    monkeypatch.setattr(get_settings(), "admin_emails", ["admin@x.com"])
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def as_user(name: str, email: str = "", verified: bool = False) -> dict[str, str]:
    value = name + (f";{email}" if email or verified else "") + (";verified" if verified else "")
    return {"X-Test-User": value}


@pytest.fixture
def learner(client) -> dict[str, str]:
    """A learner who has already given consent."""
    h = as_user("alice")
    assert client.post("/api/me/consent", headers=h).status_code == 200
    return h
