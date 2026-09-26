"""P4 PDF reports, P5 learner groups and weight-impact preview."""

from datetime import date

import pytest

from app.services import clustering
from app.services.report_pdf import clean
from app.services.scoring import ActivityInput
from tests.conftest import as_user
from tests.test_activities import PDF, _activity
from tests.test_educator import _consented, admin, educator  # noqa: F401  (fixtures)

KEYS = ["technical", "leadership", "research"]
W = {"project": {"technical": 1.0}, "club_role": {"leadership": 1.0}, "paper": {"research": 1.0}}
LABELS = {"technical": "Technical", "leadership": "Leadership", "research": "Research"}
TODAY = date(2026, 9, 26)


# ---------- clustering service ----------
def _history(i, type_key, n, persona=None, months_ago=range(12)):
    acts = tuple(
        ActivityInput(i * 100 + j, "x", type_key, date(2026, 9 - (m % 9), 1) if m < 9 else date(2025, 12 - (m - 9), 1), None, "lead", "institute", "verified")
        for j, m in zip(range(n), months_ago, strict=False)
    )
    return clustering.LearnerHistory(i, acts, persona)


def test_group_learners_separates_profile_types():
    learners = [_history(i, "project", 6, "coder") for i in range(6)] + [_history(10 + i, "club_role", 6, "leader") for i in range(6)]
    g = clustering.group_learners(learners, W, KEYS, LABELS, TODAY, k=2)
    now = {lid: s[-1] for lid, s in g.assignments.items()}
    assert len({now[i] for i in range(6)}) == 1 and len({now[10 + i] for i in range(6)}) == 1
    assert now[0] != now[10]
    names = {gr.id: gr.name for gr in g.groups}
    assert "Technical" in names[now[0]] and "Leadership" in names[now[10]]
    assert g.persona_agreement["ari"] == pytest.approx(1.0)
    assert [a.name.split(" ")[0] for a in g.algorithms] == ["K-Means", "Agglomerative", "DBSCAN"]
    assert len(g.period_dates) == 3 and len(g.transitions) == 2
    assert all(len(p) == 2 for p in g.pca.values())


def test_group_learners_auto_k_and_inactive_state():
    learners = [_history(i, t, 6) for i, t in enumerate(["project", "club_role", "paper"] * 3)]
    learners.append(clustering.LearnerHistory(99, ()))
    g = clustering.group_learners(learners, W, KEYS, LABELS, TODAY)
    assert 2 <= g.k <= 8 and g.notes and g.persona_agreement is None
    assert g.assignments[99] == [clustering.INACTIVE] * 3
    assert 99 not in g.pca


def test_group_learners_needs_enough_learners():
    with pytest.raises(clustering.NotEnoughLearners):
        clustering.group_learners([_history(i, "project", 3) for i in range(3)], W, KEYS, LABELS, TODAY)


# ---------- API: groups ----------
def test_groups_endpoint_on_demo_learners(client, admin, educator):  # noqa: F811
    client.post("/api/admin/synthetic", headers=admin, json={"learners": 30, "seed": 3})
    res = client.get("/api/educator/groups", headers=educator, params={"synthetic": "only"})
    assert res.status_code == 200
    g = res.json()
    assert 2 <= g["k"] <= 8 and len(g["groups"]) == g["k"]
    assert sum(gr["size"] for gr in g["groups"]) == sum(m["states"][-1] >= 0 for m in g["members"])
    assert len(g["members"]) == 30 and g["persona_agreement"]["ari"] > 0
    assert len(g["transitions"]) == 2 and g["k_selection"][0]["k"] == 2
    fixed = client.get("/api/educator/groups", headers=educator, params={"synthetic": "only", "k": 3}).json()
    assert fixed["k"] == 3 and not fixed["notes"]


def test_groups_endpoint_errors(client, learner, educator):  # noqa: F811
    assert client.get("/api/educator/groups", headers=learner).status_code == 403
    res = client.get("/api/educator/groups", headers=educator, params={"synthetic": "exclude"})
    assert res.status_code == 422 and "At least" in res.json()["detail"]


# ---------- API: weight preview ----------
def test_weight_preview_does_not_save(client, admin, learner):  # noqa: F811
    for i in range(3):
        _activity(client, learner, title=f"p{i}")
    bob = as_user("bob", "bob@x.com")
    _consented(client, bob)
    types = client.get("/api/activity-types", headers=bob).json()
    club = next(t for t in types if t["key"] == "club_role")
    _activity(client, bob, type_id=club["id"])

    res = client.post("/api/admin/weights/preview", headers=admin, json={"weights": {"project": {"leadership": 1.0}}})
    assert res.status_code == 200
    body = res.json()
    assert body["learners"] == 2 and body["changed_weights"] == 1
    lead = next(c for c in body["competencies"] if c["key"] == "leadership")
    assert lead["mean_change"] > 0 and lead["kendall_tau"] is not None
    assert body["top_changed"] >= 1  # alice's projects now count strongly for leadership too
    cfg = client.get("/api/competencies/config", headers=admin).json()
    assert cfg["weights"]["project"]["leadership"] == 0.2  # unchanged
    assert client.post("/api/admin/weights/preview", headers=admin, json={"weights": {"project": {"leadership": 2}}}).status_code == 422


# ---------- API: PDF report ----------
def test_pdf_report_learner_and_educator(client, learner, educator):  # noqa: F811
    aid = _activity(client, learner, title="Café − AI → ML ✓").json()["id"]
    client.post(f"/api/me/activities/{aid}/evidence", headers=learner, files={"file": ("c.pdf", PDF)})
    client.post("/api/me/academics", headers=learner, json={"semester": 1, "course_code": "CS1", "course_name": "C", "credits": 4, "grade": "A+"})
    client.post("/api/me/interests", headers=learner, json={"tag": "Cloud", "level": 4})
    client.patch("/api/me", headers=learner, json={"name": "அருண் Kumar", "register_no": "RA25/001"})

    res = client.get("/api/me/report.pdf", headers=learner)
    assert res.status_code == 200 and res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF") and len(res.content) > 3000
    assert 'filename="competency-report-RA25-001-' in res.headers["content-disposition"]

    uid = client.get("/api/me", headers=learner).json()["id"]
    assert client.get(f"/api/educator/learners/{uid}/report.pdf", headers=educator).status_code == 200
    assert client.get(f"/api/educator/learners/{uid}/report.pdf", headers=learner).status_code == 403
    assert client.get("/api/educator/learners/9999/report.pdf", headers=educator).status_code == 404


def test_pdf_report_empty_learner(client, learner):
    res = client.get("/api/me/report.pdf", headers=learner)
    assert res.status_code == 200 and res.content.startswith(b"%PDF")


def test_clean_keeps_pdf_text_safe():
    assert clean("A − B → C ≥ 1 & <x>") == "A - B -&gt; C &gt;= 1 &amp; &lt;x&gt;"
    assert "?" in clean("அருண்")
