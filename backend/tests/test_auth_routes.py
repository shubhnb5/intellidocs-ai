"""Integration tests for /api/auth/* against the real service layer (not
faked) -- unlike most other route tests, these routes ARE what's under
test. DB is in-memory SQLite (db_session) and Redis is fakeredis (autouse
fake_redis, see conftest.py), so no live service is needed either way.
"""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _register(email: str = "user@example.com", password: str = "hunter2hunter"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def test_register_returns_a_token_pair(db_session):
    response = _register()

    assert response.status_code == 201
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_register_rejects_a_duplicate_email(db_session):
    _register(email="dupe@example.com")

    response = _register(email="dupe@example.com")

    assert response.status_code == 409
    assert response.json()["error"]["type"] == "email_already_registered"


def test_login_returns_a_token_pair_for_correct_credentials(db_session):
    _register(email="login@example.com", password="correcthorsebattery")

    response = client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "correcthorsebattery"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_rejects_the_wrong_password(db_session):
    _register(email="wrongpw@example.com", password="correcthorsebattery")

    response = client.post(
        "/api/auth/login", json={"email": "wrongpw@example.com", "password": "nope12345"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["type"] == "authentication_error"


def test_login_rejects_an_unknown_email(db_session):
    response = client.post(
        "/api/auth/login", json={"email": "ghost@example.com", "password": "whatever1"}
    )

    assert response.status_code == 401


def test_me_requires_a_valid_access_token(db_session):
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["type"] == "authentication_error"


def test_me_returns_the_authenticated_user(db_session):
    tokens = _register(email="me@example.com").json()

    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


def test_refresh_issues_a_new_pair_and_rotates_the_old_refresh_token(db_session):
    tokens = _register(email="refresh@example.com").json()

    refreshed = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    # The old refresh token was rotated out -- reusing it now fails, which
    # is what makes rotation actually mean something (see services/auth.py).
    reused = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reused.status_code == 401


def test_refresh_rejects_a_garbage_token(db_session):
    response = client.post("/api/auth/refresh", json={"refresh_token": "not-a-real-token"})

    assert response.status_code == 401


def test_logout_revokes_the_refresh_token(db_session):
    tokens = _register(email="logout@example.com").json()

    logout_response = client.post(
        "/api/auth/logout", json={"refresh_token": tokens["refresh_token"]}
    )
    assert logout_response.status_code == 204

    reused = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reused.status_code == 401
