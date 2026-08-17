"""Redis connection — one client shared by three unrelated-looking but
genuinely-the-same-primitive uses: the refresh-token allowlist (services/
auth.py), the documents-list cache (services/document_cache.py), and
fixed-window rate limit counters (core/rate_limit.py). All three are just
"a key with a TTL", which is exactly what Redis is for.
"""

from functools import lru_cache

import redis.asyncio as redis

from src.core.config import get_settings


@lru_cache
def get_redis_client() -> redis.Redis:
    """Cached so every request reuses one connection pool instead of
    opening a new connection per call. decode_responses=True so callers get
    str back, not bytes — every value this app stores in Redis is text."""
    settings = get_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)
