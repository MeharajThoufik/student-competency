from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["database"] in {"ok", "unavailable", "not_configured"}


def test_docs_served_under_api():
    assert client.get("/api/openapi.json").status_code == 200
