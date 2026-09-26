import pytest

from tests.conftest import as_user
from tests.test_activities import PDF, _activity

ALL_COMPETENCIES = [
    "technical", "problem_solving", "communication", "leadership",
    "collaboration", "creativity", "research", "continuous_learning",
]  # fmt: skip


def _consented(client, headers):
    client.post("/api/me/consent", headers=headers)
    return client.get("/api/me", headers=headers).json()


@pytest.fixture
def admin(client):
    h = as_user("root", "admin@x.com", verified=True)
    assert _consented(client, h)["role"] == "admin"
    return h


@pytest.fixture
def educator(client, admin):
    h = as_user("prof", "prof@x.com")
    uid = _consented(client, h)["id"]
    assert client.patch(f"/api/admin/users/{uid}", headers=admin, json={"role": "educator"}).status_code == 200
    return h


def _with_evidence(client, headers, **kw):
    aid = _activity(client, headers, **kw).json()["id"]
    client.post(f"/api/me/activities/{aid}/evidence", headers=headers, files={"file": ("c.pdf", PDF)})
    return aid


def _scores(client, headers):
    return {s["key"]: s["score"] for s in client.get("/api/me/competencies", headers=headers).json()["scores"]}


# ---------- access control ----------
@pytest.mark.parametrize("path", ["/api/educator/queue", "/api/educator/learners", "/api/educator/cohort"])
def test_learner_cannot_use_educator_api(client, learner, path):
    assert client.get(path, headers=learner).status_code == 403


def test_educator_cannot_use_admin_api(client, educator):
    assert client.get("/api/admin/users", headers=educator).status_code == 403
    assert client.put("/api/admin/weights", headers=educator, json={"weights": {}}).status_code == 403


# ---------- review ----------
def test_review_queue_and_verify(client, learner, educator):
    _activity(client, learner, title="No evidence")
    aid = _with_evidence(client, learner)
    queue = client.get("/api/educator/queue", headers=educator).json()
    assert queue["total"] == 1 and queue["items"][0]["activity"]["id"] == aid
    assert queue["items"][0]["learner"]["name"] == "alice"

    before = _scores(client, learner)
    res = client.post(f"/api/educator/activities/{aid}/review", headers=educator, json={"decision": "verify", "note": "Checked"})
    assert res.status_code == 200 and res.json()["evidence_status"] == "verified"
    assert _scores(client, learner)["technical"] > before["technical"]

    assert client.get("/api/educator/queue", headers=educator).json()["total"] == 0
    verified = client.get("/api/educator/queue", headers=educator, params={"status": "verified"}).json()
    assert verified["items"][0]["activity"]["review_note"] == "Checked"
    snaps = client.get("/api/me/competencies/snapshots", headers=learner).json()
    assert snaps[-1]["trigger"] == "activity_verified"


def test_reject_requires_note_and_is_audited(client, learner, educator, admin):
    aid = _with_evidence(client, learner)
    url = f"/api/educator/activities/{aid}/review"
    assert client.post(url, headers=educator, json={"decision": "reject"}).status_code == 422
    assert client.post(url, headers=educator, json={"decision": "reject", "note": "  "}).status_code == 422
    before = _scores(client, learner)
    res = client.post(url, headers=educator, json={"decision": "reject", "note": "Certificate is unreadable"})
    assert res.json()["verification_status"] == "rejected"
    assert _scores(client, learner)["technical"] < before["technical"]
    assert client.get(f"/api/me/activities/{aid}", headers=learner).json()["review_note"] == "Certificate is unreadable"
    log = client.get("/api/admin/audit", headers=admin).json()
    assert log[0]["action"] == "activity_rejected" and log[0]["actor"] == "prof@x.com"
    assert log[0]["details"]["note"] == "Certificate is unreadable"


def test_cannot_review_own_activity(client, admin):
    aid = _activity(client, admin).json()["id"]
    res = client.post(f"/api/educator/activities/{aid}/review", headers=admin, json={"decision": "verify"})
    assert res.status_code == 403


def test_review_unknown_activity(client, educator):
    res = client.post("/api/educator/activities/999/review", headers=educator, json={"decision": "verify"})
    assert res.status_code == 404


# ---------- learners ----------
def test_learner_list_and_risks(client, learner, educator):
    _activity(client, learner, start_date="2025-01-10")  # old -> inactive
    bob = as_user("bob", "bob@x.com")
    _consented(client, bob)
    body = client.get("/api/educator/learners", headers=educator).json()
    rows = {r["learner"]["name"]: r for r in body["items"]}
    assert set(rows) == {"alice", "bob"}  # staff accounts are not listed
    assert rows["alice"]["risks"] == ["inactive"] and rows["bob"]["risks"] == ["no_activity"]
    assert rows["alice"]["top_competency"] == "technical"
    assert "inactive" in body["risk_rules"]

    only_alice = client.get("/api/educator/learners", headers=educator, params={"q": "ali"}).json()
    assert [r["learner"]["name"] for r in only_alice["items"]] == ["alice"]
    by_score = client.get("/api/educator/learners", headers=educator, params={"sort": "mean_score"}).json()
    assert by_score["items"][0]["learner"]["name"] == "alice"
    risky = client.get("/api/educator/learners", headers=educator, params={"at_risk": True}).json()
    assert risky["total"] == 2


def test_learner_detail(client, learner, educator):
    aid = _with_evidence(client, learner)
    me = client.get("/api/me", headers=learner).json()
    d = client.get(f"/api/educator/learners/{me['id']}", headers=educator).json()
    assert d["profile"]["name"] == "alice" and d["profile"]["synthetic"] is False
    assert d["activities"][0]["id"] == aid and d["activities"][0]["evidence"]
    assert d["insights"]["activity_count"] == 1
    ev = d["activities"][0]["evidence"][0]["id"]
    assert client.get(f"/api/evidence/{ev}/file", headers=educator).status_code == 200


def test_learner_detail_rejects_staff_and_unknown(client, educator, admin):
    admin_id = client.get("/api/me", headers=admin).json()["id"]
    assert client.get(f"/api/educator/learners/{admin_id}", headers=educator).status_code == 404
    assert client.get("/api/educator/learners/9999", headers=educator).status_code == 404


def test_cohort(client, learner, educator):
    _with_evidence(client, learner)
    _activity(client, learner, title="Two")
    c = client.get("/api/educator/cohort", headers=educator).json()
    assert c["learner_count"] == 1 and c["active_count"] == 1
    tech = next(x for x in c["competencies"] if x["key"] == "technical")
    assert tech["minimum"] == tech["median"] == tech["maximum"] > 0
    assert sum(tech["trends"].values()) == 1
    assert c["evidence"]["evidence_attached"] == 1 and c["evidence"]["self_reported"] == 1
    assert c["activity_types"][0] == {"key": "project", "label": "Project", "count": 2}


# ---------- admin ----------
def test_roles(client, admin, learner):
    users = {u["email"]: u for u in client.get("/api/admin/users", headers=admin).json()}
    me = users["admin@x.com"]
    assert client.patch(f"/api/admin/users/{me['id']}", headers=admin, json={"role": "learner"}).status_code == 409
    alice = next(u for u in users.values() if u["name"] == "alice")
    assert client.patch(f"/api/admin/users/{alice['id']}", headers=admin, json={"role": "boss"}).status_code == 422
    assert client.patch("/api/admin/users/9999", headers=admin, json={"role": "educator"}).status_code == 404
    assert [u["email"] for u in client.get("/api/admin/users", headers=admin, params={"role": "admin"}).json()] == ["admin@x.com"]


def test_role_change_takes_effect_immediately(client, admin, learner):
    alice = client.get("/api/me", headers=learner).json()
    assert client.get("/api/educator/learners", headers=learner).status_code == 403
    client.patch(f"/api/admin/users/{alice['id']}", headers=admin, json={"role": "educator"})
    assert client.get("/api/educator/learners", headers=learner).status_code == 200
    assert client.get("/api/admin/audit", headers=admin).json()[0]["details"]["new"] == "educator"


def test_weights_update_validate_and_reset(client, admin, learner):
    _activity(client, learner)
    base = _scores(client, learner)["research"]
    res = client.put("/api/admin/weights", headers=admin, json={"weights": {"project": {"research": 1.0}}})
    assert res.status_code == 200 and res.json()["project"]["research"] == 1.0
    assert _scores(client, learner)["research"] > base

    bad = [
        {"project": {"research": 1.5}},
        {"nope": {"research": 0.5}},
        {"project": {"nope": 0.5}},
        {"award": {k: 0 for k in ALL_COMPETENCIES}},
    ]
    for weights in bad:
        assert client.put("/api/admin/weights", headers=admin, json={"weights": weights}).status_code == 422

    assert client.post("/api/admin/weights/reset", headers=admin).json()["project"]["research"] == 0.3
    assert _scores(client, learner)["research"] == base
    actions = [a["action"] for a in client.get("/api/admin/audit", headers=admin).json()]
    assert actions[:2] == ["weights_reset", "weights_updated"]
    log = client.get("/api/admin/audit", headers=admin, params={"action": "weights_updated"}).json()
    assert log[0]["details"]["changes"] == {"project": {"research": [0.3, 1.0]}}
