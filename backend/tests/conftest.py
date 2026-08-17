"""Shared test fixtures.

db_session gives each test an isolated in-memory SQLite database and swaps
it in for the app's real get_db_session dependency, so route tests never
touch (or need) the on-disk intellidocs.db file.

fake_redis (Phase 8) is autouse: once auth landed, nearly every route test
now transitively depends on Redis too (rate limiting runs as a dependency
on every protected route, whether or not a given test cares about limits),
so — same reasoning as never hitting a real Qdrant/Claude/MCP — no test in
this suite should ever need a live Redis server either.

current_user (Phase 8) overrides the auth dependencies with a fixed test
user, for the many tests that care about a route's own logic, not about
authentication itself (see test_auth_routes.py for tests of auth itself).
"""

import pytest
from fakeredis import FakeAsyncRedis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from src.core import rate_limit as rate_limit_module
from src.core.auth_dependency import CurrentUser, get_current_user, get_current_user_or_internal
from src.db.database import get_db_session
from src.db.sql_models import Base
from src.routes import document_routes as documents_module
from src.routes import health_routes as health_module
from src.services import auth as auth_service_module

TEST_USER = CurrentUser(user_id="test-user-id", email="test@example.com")


@pytest.fixture
def db_session():
    # StaticPool: an in-memory SQLite database only exists on the connection
    # that created it. TestClient runs each request on a different thread
    # than this fixture, so without StaticPool (one shared connection for
    # every thread) that request would see a separate, empty database.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()

    def override_get_db_session():
        try:
            yield session
        finally:
            pass  # closed below, once, after the test — not per-request

    app.dependency_overrides[get_db_session] = override_get_db_session
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides.pop(get_db_session, None)


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    # decode_responses=True to match the real client (src/db/redis_client.py)
    # -- without it, .get() returns bytes instead of str, and refresh-token
    # rotation's stored_user_id != user_id check would always be True.
    fake = FakeAsyncRedis(decode_responses=True)
    for module in (rate_limit_module, documents_module, health_module, auth_service_module):
        monkeypatch.setattr(module, "get_redis_client", lambda: fake)
    yield fake


@pytest.fixture
def current_user():
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    app.dependency_overrides[get_current_user_or_internal] = lambda: TEST_USER
    try:
        yield TEST_USER
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_current_user_or_internal, None)
