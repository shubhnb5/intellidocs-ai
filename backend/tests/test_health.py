from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_check_returns_ok():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "app_name" in body
    assert body["qdrant"] in ("ok", "unreachable")
    assert body["mcp_server"] in ("ok", "unreachable")
    assert body["redis"] == "ok"  # fake_redis (conftest.py, autouse) is always reachable


def test_response_carries_request_id_header():
    response = client.get("/api/health")
    assert "x-request-id" in response.headers


def test_unknown_route_returns_404():
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
