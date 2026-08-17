"""Unit tests for the pure hashing/JWT functions in services/security.py --
no DB, no Redis, no network, so nothing here needs mocking.
"""

import pytest

from src.core.exceptions import AuthenticationError
from src.services import security


def test_hash_password_roundtrip():
    hashed = security.hash_password("correct horse battery staple")
    assert security.verify_password("correct horse battery staple", hashed)


def test_verify_password_rejects_wrong_password():
    hashed = security.hash_password("correct horse battery staple")
    assert not security.verify_password("wrong password", hashed)


def test_create_and_decode_access_token_roundtrip():
    token = security.create_access_token(user_id="user-1", email="a@example.com")
    payload = security.decode_token(token, expected_type="access")
    assert payload["sub"] == "user-1"
    assert payload["email"] == "a@example.com"
    assert payload["type"] == "access"


def test_create_and_decode_refresh_token_roundtrip():
    token, jti, _expires_at = security.create_refresh_token(user_id="user-1")
    payload = security.decode_token(token, expected_type="refresh")
    assert payload["sub"] == "user-1"
    assert payload["jti"] == jti
    assert payload["type"] == "refresh"


def test_decode_token_rejects_the_wrong_token_type():
    access_token = security.create_access_token(user_id="user-1", email="a@example.com")
    with pytest.raises(AuthenticationError):
        security.decode_token(access_token, expected_type="refresh")


def test_decode_token_rejects_garbage():
    with pytest.raises(AuthenticationError):
        security.decode_token("not-a-real-token", expected_type="access")


def test_decode_token_rejects_an_expired_token(monkeypatch):
    settings = security.get_settings()
    monkeypatch.setattr(settings, "jwt_access_token_expire_minutes", -1)

    token = security.create_access_token(user_id="user-1", email="a@example.com")

    with pytest.raises(AuthenticationError):
        security.decode_token(token, expected_type="access")
