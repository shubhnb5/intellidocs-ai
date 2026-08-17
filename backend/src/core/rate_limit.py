"""Fixed-window rate limiting via Redis INCR+EXPIRE.

Fixed-window, not sliding-window/token-bucket: one INCR plus one EXPIRE per
request is enough to demonstrate the pattern and is exactly what a Redis-
backed limiter is *for*, without pulling in a library. The known trade-off
is a burst at window boundaries (up to 2x the limit across a boundary) —
acceptable for protecting a portfolio-scope demo from accidental hammering,
not tuned as a hardened abuse defense.

Keyed by client IP, not by user, so it also covers the unauthenticated
login/register endpoints (the classic brute-force targets) — the trade-off
is that everyone behind one NAT/proxy shares a bucket, worth naming as a
known limitation rather than a design that scales to production traffic.
"""

from fastapi import Request

from src.core.exceptions import RateLimitExceededError
from src.db.redis_client import get_redis_client

RATE_LIMIT_KEY_PREFIX = "ratelimit:"


async def check_rate_limit(*, scope: str, identifier: str, limit: int, window_seconds: int) -> None:
    key = f"{RATE_LIMIT_KEY_PREFIX}{scope}:{identifier}"
    redis_client = get_redis_client()

    current = await redis_client.incr(key)
    if current == 1:
        await redis_client.expire(key, window_seconds)

    if current > limit:
        raise RateLimitExceededError(
            f"Too many requests. Limit is {limit} per {window_seconds}s — try again shortly."
        )


class RateLimiter:
    """A parameterized FastAPI dependency: `Depends(RateLimiter(limit=20,
    window_seconds=60, scope="chat_ask"))`. A class (not a plain function)
    specifically so each route can configure its own limit/window/scope
    while still being a single `Depends(...)` callable — a plain function
    can't take route-specific config without a factory wrapper, which this
    just is, spelled as a class instead."""

    def __init__(self, *, limit: int, window_seconds: int, scope: str) -> None:
        self._limit = limit
        self._window_seconds = window_seconds
        self._scope = scope

    async def __call__(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        await check_rate_limit(
            scope=self._scope,
            identifier=client_ip,
            limit=self._limit,
            window_seconds=self._window_seconds,
        )
