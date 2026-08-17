"""Unit tests for the fixed-window rate limiter, calling check_rate_limit
directly against the (autouse, fake) Redis instance rather than through
HTTP -- this is about the counting logic itself, not which routes happen to
have a limiter attached. See test_auth_routes.py / test_documents.py /
test_chat_route.py for confirmation that the limiter is actually wired in.
"""

import pytest

from src.core.exceptions import RateLimitExceededError
from src.core.rate_limit import check_rate_limit


async def test_allows_requests_up_to_the_limit(fake_redis):
    for _ in range(3):
        await check_rate_limit(scope="test", identifier="ip-1", limit=3, window_seconds=60)


async def test_blocks_the_request_after_the_limit(fake_redis):
    for _ in range(3):
        await check_rate_limit(scope="test", identifier="ip-1", limit=3, window_seconds=60)

    with pytest.raises(RateLimitExceededError):
        await check_rate_limit(scope="test", identifier="ip-1", limit=3, window_seconds=60)


async def test_different_identifiers_have_independent_buckets(fake_redis):
    for _ in range(3):
        await check_rate_limit(scope="test", identifier="ip-1", limit=3, window_seconds=60)

    # ip-2's bucket is untouched by ip-1's usage.
    await check_rate_limit(scope="test", identifier="ip-2", limit=3, window_seconds=60)


async def test_different_scopes_have_independent_buckets(fake_redis):
    for _ in range(3):
        await check_rate_limit(scope="login", identifier="ip-1", limit=3, window_seconds=60)

    # Same identifier, different scope (e.g. chat vs. login) -- own bucket.
    await check_rate_limit(scope="upload", identifier="ip-1", limit=3, window_seconds=60)


async def test_window_resets_once_the_key_expires(fake_redis):
    await check_rate_limit(scope="test", identifier="ip-1", limit=1, window_seconds=60)
    with pytest.raises(RateLimitExceededError):
        await check_rate_limit(scope="test", identifier="ip-1", limit=1, window_seconds=60)

    # Simulate the window elapsing instead of sleeping 60s in a test.
    await fake_redis.delete("ratelimit:test:ip-1")

    await check_rate_limit(scope="test", identifier="ip-1", limit=1, window_seconds=60)
