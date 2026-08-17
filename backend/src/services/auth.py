"""Registration, login, and refresh-token lifecycle — the orchestration
layer that combines services/security.py's pure hashing/JWT functions with
the SQL users table and Redis's refresh-token allowlist.

Refresh tokens are allowlisted in Redis (key `refresh_token:{jti}` ->
user_id, TTL = the token's own expiry) rather than trusted purely on
signature, specifically so logout and rotation can actually revoke one:
a stateless JWT alone can't be un-issued before it expires.

Refresh token *rotation*: every successful refresh deletes the old jti and
issues a brand new access+refresh pair. This means a stolen refresh token
only works once before the legitimate client's next refresh call fails
(a strong signal of theft, in a real system worth alerting on) — plain
non-rotating refresh tokens don't give you that.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.core.exceptions import AuthenticationError, EmailAlreadyRegisteredError
from src.db.redis_client import get_redis_client
from src.db.sql_models import UserRecord
from src.services.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

REFRESH_TOKEN_KEY_PREFIX = "refresh_token:"


class TokenPair:
    def __init__(self, access_token: str, refresh_token: str) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token


async def register_user(db: Session, *, email: str, password: str) -> UserRecord:
    if db.query(UserRecord).filter(UserRecord.email == email).first() is not None:
        raise EmailAlreadyRegisteredError(f"An account with email '{email}' already exists.")

    user = UserRecord(
        user_id=str(uuid.uuid4()),
        email=email,
        hashed_password=hash_password(password),
        created_at=datetime.now(UTC),
    )
    db.add(user)
    db.commit()
    return user


async def authenticate_user(db: Session, *, email: str, password: str) -> UserRecord:
    user = db.query(UserRecord).filter(UserRecord.email == email).first()
    if user is None or not verify_password(password, user.hashed_password):
        # Same message for "no such user" and "wrong password" -- a
        # different message would let an attacker enumerate registered
        # emails one guess at a time.
        raise AuthenticationError("Incorrect email or password.")
    return user


async def issue_token_pair(*, user_id: str, email: str) -> TokenPair:
    access_token = create_access_token(user_id=user_id, email=email)
    refresh_token, jti, expires_at = create_refresh_token(user_id=user_id)

    ttl_seconds = max(1, int((expires_at - datetime.now(UTC)).total_seconds()))
    await get_redis_client().set(f"{REFRESH_TOKEN_KEY_PREFIX}{jti}", user_id, ex=ttl_seconds)

    return TokenPair(access_token=access_token, refresh_token=refresh_token)


async def refresh_token_pair(db: Session, *, refresh_token: str) -> TokenPair:
    payload = decode_token(refresh_token, expected_type="refresh")
    jti, user_id = payload["jti"], payload["sub"]

    redis_client = get_redis_client()
    stored_user_id = await redis_client.get(f"{REFRESH_TOKEN_KEY_PREFIX}{jti}")
    if stored_user_id is None or stored_user_id != user_id:
        # Valid signature, but not (or no longer) in the allowlist -- already
        # used once (rotation), logged out, or expired server-side.
        raise AuthenticationError("Invalid or expired token.")

    user = db.get(UserRecord, user_id)
    if user is None:
        raise AuthenticationError("Invalid or expired token.")

    await redis_client.delete(f"{REFRESH_TOKEN_KEY_PREFIX}{jti}")  # rotate: old token dies here
    return await issue_token_pair(user_id=user.user_id, email=user.email)


async def revoke_refresh_token(*, refresh_token: str) -> None:
    """Logout. Ignores expiry when decoding -- revoking an already-expired
    token is harmless and shouldn't itself fail with an error the frontend
    has to handle specially."""
    payload = decode_token(refresh_token, expected_type="refresh", verify_exp=False)
    await get_redis_client().delete(f"{REFRESH_TOKEN_KEY_PREFIX}{payload['jti']}")
