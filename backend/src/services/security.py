"""Password hashing and JWT encode/decode — pure, dependency-free functions
(no DB, no Redis, no network), so they're unit-testable directly without
mocking anything. Higher-level orchestration (checking a user exists,
tracking refresh tokens) lives in services/auth.py, which calls these.

bcrypt directly, not passlib: passlib is effectively unmaintained and its
bcrypt backend has had version-compatibility breaks with recent bcrypt
releases. Calling the bcrypt package directly is one fewer moving part.

PyJWT, not python-jose: smaller, actively maintained, and this project only
needs HS256 sign/verify — none of jose's extra JWE/JWK surface.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import bcrypt
import jwt

from src.core.config import get_settings
from src.core.exceptions import AuthenticationError

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(*, user_id: str, email: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(*, user_id: str) -> tuple[str, str, datetime]:
    """Returns (token, jti, expires_at) — the caller (services/auth.py)
    stores jti -> user_id in Redis so refresh tokens can be revoked/rotated,
    something a purely stateless JWT can't support on its own."""
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=settings.jwt_refresh_token_expire_days)
    jti = str(uuid.uuid4())
    payload = {"sub": user_id, "type": "refresh", "iat": now, "exp": expires_at, "jti": jti}
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def decode_token(token: str, *, expected_type: TokenType, verify_exp: bool = True) -> dict:
    """Verifies signature (and, unless disabled, expiry) and the token's
    `type` claim, raising one uniform AuthenticationError for every failure
    mode — see that class's docstring for why callers don't need to
    distinguish "expired" from "malformed" from "wrong type"."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": verify_exp},
        )
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid or expired token.") from exc

    if payload.get("type") != expected_type:
        raise AuthenticationError("Invalid or expired token.")
    return payload
