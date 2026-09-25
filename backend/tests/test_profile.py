from tests.conftest import as_user


def test_requires_token(client):
    assert client.get("/api/me").status_code == 401


def test_first_login_creates_learner(client):
    res = client.get("/api/me", headers=as_user("bob"))
    assert res.status_code == 200
    body = res.json()
    assert body["role"] == "learner"
    assert body["email"] == "bob@example.com"
    assert body["consent_given_at"] is None


def test_admin_bootstrap_requires_verified_email(client):
    assert client.get("/api/me", headers=as_user("eve", "admin@x.com")).json()["role"] == "learner"
    assert client.get("/api/me", headers=as_user("root", "admin@x.com", verified=True)).json()["role"] == "admin"


def test_consent_gate(client):
    h = as_user("carol")
    assert client.get("/api/me/skills", headers=h).status_code == 403
    assert client.post("/api/me/consent", headers=h).json()["consent_given_at"] is not None
    assert client.get("/api/me/skills", headers=h).status_code == 200


def test_update_profile(client, learner):
    res = client.patch("/api/me", headers=learner, json={"programme": "M.Tech CCB", "batch": "2025-2027"})
    assert res.status_code == 200
    assert res.json()["programme"] == "M.Tech CCB"
    assert res.json()["name"] == "alice"


def test_academics_and_gpa(client, learner):
    rows = [
        {"semester": 1, "course_code": "C1", "course_name": "Cloud", "credits": 4, "grade": "O"},
        {"semester": 1, "course_code": "C2", "course_name": "Blockchain", "credits": 2, "grade": "B"},
        {"semester": 2, "course_code": "C3", "course_name": "ML", "credits": 3, "grade": "A+"},
    ]
    for r in rows:
        assert client.post("/api/me/academics", headers=learner, json=r).status_code == 201
    assert client.post("/api/me/academics", headers=learner, json=rows[0]).status_code == 409

    summary = client.get("/api/me/academics/summary", headers=learner).json()
    assert summary["semesters"][0] == {"semester": 1, "credits": 6.0, "sgpa": round((40 + 12) / 6, 2)}
    assert summary["cgpa"] == round((40 + 12 + 27) / 9, 2)
    assert summary["total_credits"] == 9


def test_invalid_grade_rejected(client, learner):
    bad = {"semester": 1, "course_code": "X", "course_name": "X", "credits": 3, "grade": "Z"}
    assert client.post("/api/me/academics", headers=learner, json=bad).status_code == 422


def test_skills_unique_and_isolated(client, learner):
    skill = {"name": "Python", "category": "technical", "self_level": 4}
    sid = client.post("/api/me/skills", headers=learner, json=skill).json()["id"]
    assert client.post("/api/me/skills", headers=learner, json=skill).status_code == 409

    other = as_user("mallory")
    client.post("/api/me/consent", headers=other)
    assert client.delete(f"/api/me/skills/{sid}", headers=other).status_code == 404
    assert client.delete(f"/api/me/skills/{sid}", headers=learner).status_code == 204


def test_interest_soft_delete_allows_readd(client, learner):
    iid = client.post("/api/me/interests", headers=learner, json={"tag": "Cloud", "level": 4}).json()["id"]
    assert client.post("/api/me/interests", headers=learner, json={"tag": "cloud", "level": 3}).status_code == 409
    assert client.delete(f"/api/me/interests/{iid}", headers=learner).status_code == 204
    assert client.get("/api/me/interests", headers=learner).json() == []
    assert client.post("/api/me/interests", headers=learner, json={"tag": "Cloud", "level": 5}).status_code == 201
