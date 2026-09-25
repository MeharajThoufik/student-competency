from datetime import date, timedelta

from app.models import User
from tests.conftest import as_user

PDF = b"%PDF-1.4\n%test\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def _activity(client, headers, **overrides):
    types = client.get("/api/activity-types", headers=headers).json()
    body = {
        "type_id": types[0]["id"],
        "title": "Competency tracker",
        "start_date": "2026-08-01",
        "outcome": "lead",
        "scope": "institute",
        "skills": ["Python", "python", " FastAPI "],
    } | overrides
    return client.post("/api/me/activities", headers=headers, json=body)


def test_activity_types_seeded(client, learner):
    types = client.get("/api/activity-types", headers=learner).json()
    assert [t["key"] for t in types][:3] == ["project", "certification", "online_course"]


def test_create_and_list_activity(client, learner):
    res = _activity(client, learner)
    assert res.status_code == 201
    body = res.json()
    assert body["type"]["key"] == "project"
    assert body["skills"] == ["Python", "FastAPI"]  # trimmed, de-duplicated case-insensitively
    assert body["evidence_status"] == "self_reported"
    assert len(client.get("/api/me/activities", headers=learner).json()) == 1


def test_activity_validation(client, learner):
    future = (date.today() + timedelta(days=2)).isoformat()
    assert _activity(client, learner, start_date=future).status_code == 422
    assert _activity(client, learner, end_date="2026-07-01").status_code == 422
    assert _activity(client, learner, type_id=9999).status_code == 422
    assert _activity(client, learner, outcome="champion").status_code == 422


def test_other_user_cannot_see_activity(client, learner):
    aid = _activity(client, learner).json()["id"]
    other = as_user("mallory")
    client.post("/api/me/consent", headers=other)
    assert client.get(f"/api/me/activities/{aid}", headers=other).status_code == 404
    assert client.delete(f"/api/me/activities/{aid}", headers=other).status_code == 404


def test_edit_resets_verification(client, learner, engine):
    from sqlalchemy.orm import Session

    from app.models import Activity

    aid = _activity(client, learner).json()["id"]
    with Session(engine) as s:
        s.get(Activity, aid).verification_status = "verified"
        s.commit()
    assert client.get(f"/api/me/activities/{aid}", headers=learner).json()["evidence_status"] == "verified"

    body = client.get(f"/api/me/activities/{aid}", headers=learner).json()
    update = {k: body[k] for k in ("title", "start_date", "outcome", "scope", "skills")} | {
        "type_id": body["type"]["id"],
        "title": "Edited",
    }
    res = client.put(f"/api/me/activities/{aid}", headers=learner, json=update)
    assert res.json()["verification_status"] == "unverified"


def test_evidence_upload_download_delete(client, learner):
    aid = _activity(client, learner).json()["id"]
    res = client.post(
        f"/api/me/activities/{aid}/evidence", headers=learner, files={"file": ("cert.pdf", PDF, "application/pdf")}
    )
    assert res.status_code == 201
    ev = res.json()
    assert ev["content_type"] == "application/pdf"
    assert len(ev["sha256"]) == 64

    activity = client.get(f"/api/me/activities/{aid}", headers=learner).json()
    assert activity["evidence_status"] == "evidence_attached"

    dl = client.get(f"/api/evidence/{ev['id']}/file", headers=learner)
    assert dl.status_code == 200 and dl.content == PDF
    assert dl.headers["x-content-type-options"] == "nosniff"

    assert client.delete(f"/api/evidence/{ev['id']}", headers=learner).status_code == 204
    assert client.get(f"/api/evidence/{ev['id']}/file", headers=learner).status_code == 404


def test_evidence_type_sniffed_from_content(client, learner):
    aid = _activity(client, learner).json()["id"]
    # Declared as PDF but actually HTML: rejected.
    res = client.post(
        f"/api/me/activities/{aid}/evidence",
        headers=learner,
        files={"file": ("x.pdf", b"<html><script>alert(1)</script>", "application/pdf")},
    )
    assert res.status_code == 415
    # Declared wrongly but actually PNG: stored as PNG.
    res = client.post(
        f"/api/me/activities/{aid}/evidence", headers=learner, files={"file": ("x.pdf", PNG, "application/pdf")}
    )
    assert res.json()["content_type"] == "image/png"


def test_evidence_size_limit(client, learner, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    aid = _activity(client, learner).json()["id"]
    big = PDF + b"0" * (1024 * 1024)
    res = client.post(f"/api/me/activities/{aid}/evidence", headers=learner, files={"file": ("big.pdf", big)})
    assert res.status_code == 413


def test_evidence_access_control(client, learner, engine):
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    aid = _activity(client, learner).json()["id"]
    eid = client.post(f"/api/me/activities/{aid}/evidence", headers=learner, files={"file": ("c.pdf", PDF)}).json()["id"]

    other = as_user("mallory")
    client.post("/api/me/consent", headers=other)
    assert client.get(f"/api/evidence/{eid}/file", headers=other).status_code == 404
    assert client.delete(f"/api/evidence/{eid}", headers=other).status_code == 404

    teacher = as_user("teacher")
    client.post("/api/me/consent", headers=teacher)
    with Session(engine) as s:
        s.scalar(select(User).where(User.firebase_uid == "uid-teacher")).role = "educator"
        s.commit()
    assert client.get(f"/api/evidence/{eid}/file", headers=teacher).status_code == 200


def test_unicode_filename_download(client, learner):
    aid = _activity(client, learner).json()["id"]
    eid = client.post(
        f"/api/me/activities/{aid}/evidence", headers=learner, files={"file": ("சான்றிதழ் cert.pdf", PDF)}
    ).json()["id"]
    res = client.get(f"/api/evidence/{eid}/file", headers=learner)
    assert res.status_code == 200
    assert "filename*=UTF-8''" in res.headers["content-disposition"]
