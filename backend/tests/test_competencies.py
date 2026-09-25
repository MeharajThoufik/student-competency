from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CompetencySnapshot, User
from app.services import synthetic
from tests.conftest import as_user
from tests.test_activities import PDF, _activity


def _scores(client, headers, **params):
    body = client.get("/api/me/competencies", headers=headers, params=params).json()
    return {s["key"]: s for s in body["scores"]}, body


def test_config_exposes_full_model(client, learner):
    cfg = client.get("/api/competencies/config", headers=learner).json()
    assert len(cfg["competencies"]) == 8
    assert cfg["weights"]["paper"]["research"] == 1.0
    assert cfg["confidence"]["verified"] > cfg["confidence"]["self_reported"]


def test_new_learner_scores_zero(client, learner):
    scores, body = _scores(client, learner)
    assert body["activity_count"] == 0
    assert len(scores) == 8 and all(s["score"] == 0 for s in scores.values())


def test_activity_raises_mapped_competencies(client, learner):
    _activity(client, learner)  # project
    scores, body = _scores(client, learner)
    assert body["activity_count"] == 1
    assert scores["technical"]["score"] > scores["problem_solving"]["score"] > scores["communication"]["score"] > 0
    c = scores["technical"]["contributions"][0]
    assert c["title"] == "Competency tracker" and c["weight"] == 0.9


def test_evidence_increases_score(client, learner):
    aid = _activity(client, learner).json()["id"]
    before = _scores(client, learner)[0]["technical"]["score"]
    client.post(f"/api/me/activities/{aid}/evidence", headers=learner, files={"file": ("c.pdf", PDF)})
    after = _scores(client, learner)[0]["technical"]["score"]
    assert after > before


def test_as_of_replay_and_future_rejected(client, learner):
    _activity(client, learner, start_date="2026-08-01")
    past, _ = _scores(client, learner, as_of="2026-07-01")
    assert past["technical"]["score"] == 0
    assert client.get("/api/me/competencies", headers=learner, params={"as_of": "2999-01-01"}).status_code == 422


def test_snapshots_recorded_on_every_change(client, learner):
    aid = _activity(client, learner).json()["id"]
    eid = client.post(f"/api/me/activities/{aid}/evidence", headers=learner, files={"file": ("c.pdf", PDF)}).json()["id"]
    client.delete(f"/api/evidence/{eid}", headers=learner)
    client.delete(f"/api/me/activities/{aid}", headers=learner)
    snaps = client.get("/api/me/competencies/snapshots", headers=learner).json()
    assert [s["trigger"] for s in snaps] == ["activity_created", "evidence_added", "evidence_removed", "activity_deleted"]
    assert snaps[1]["scores"]["technical"] > snaps[0]["scores"]["technical"]
    assert snaps[-1]["scores"]["technical"] == 0


def test_admin_synthetic_requires_admin(client, learner):
    assert client.post("/api/admin/synthetic", headers=learner, json={"learners": 3}).status_code == 403


def test_synthetic_generation(client, engine):
    admin = as_user("root", "admin@x.com", verified=True)
    client.post("/api/me/consent", headers=admin)
    res = client.post("/api/admin/synthetic", headers=admin, json={"learners": 25, "seed": 7})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 25 and set(body["by_persona"]) <= set(synthetic.PERSONA_KEYS)

    with Session(engine) as s:
        assert s.scalar(select(func.count()).select_from(User).where(User.synthetic_persona.is_not(None))) == 25
        assert s.scalar(select(func.count()).select_from(CompetencySnapshot)) > 25

    # Deterministic: the same seed gives the same persona mix.
    assert client.post("/api/admin/synthetic", headers=admin, json={"learners": 25, "seed": 7}).json() == body
    assert client.delete("/api/admin/synthetic", headers=admin).json()["total"] == 0
    assert client.get("/api/admin/synthetic", headers=admin).json()["total"] == 0


def test_synthetic_personas_follow_intended_trajectories(engine):
    """Coarse ground-truth check on the generated data."""
    with Session(engine) as s:
        synthetic.generate(s, learners=150, seed=1)
        users = s.scalars(select(User).where(User.synthetic_persona.is_not(None))).all()

        def final(u: User) -> dict[str, float]:
            q = select(CompetencySnapshot).where(CompetencySnapshot.user_id == u.id).order_by(CompetencySnapshot.taken_at.desc())
            return s.scalars(q).first().scores

        def mean(persona: str, key: str) -> float:
            vals = [final(u)[key] for u in users if u.synthetic_persona == persona]
            return sum(vals) / len(vals)

        assert mean("coder", "technical") > mean("leader", "technical")
        assert mean("leader", "leadership") > mean("coder", "leadership")
        assert mean("researcher", "research") > mean("all_rounder", "research")
        assert mean("fading", "technical") < mean("coder", "technical")
