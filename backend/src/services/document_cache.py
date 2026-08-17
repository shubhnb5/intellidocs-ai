"""Cache-aside for GET /api/documents: one JSON blob per user in Redis.

Two invalidation paths, deliberately: a short TTL as a staleness backstop
for any writer that isn't document_routes.py's own upload handler, and an
explicit delete right after a successful upload as the primary path (so a
user who just uploaded sees it in their list immediately, not up-to-30s
later). Kept out of routes/document_routes.py so the caching concern
-- and its own tests -- don't get tangled with the upload/list/detail
route logic.

DocumentSummary lives here rather than in document_routes.py: this module
needs it to (de)serialize the cached list, and document_routes.py already
imports this module, so defining it there instead would make the two
modules import each other.
"""

import json
from datetime import datetime

import redis.asyncio as redis
from pydantic import BaseModel

_CACHE_KEY_PREFIX = "documents:"


class DocumentSummary(BaseModel):
    document_id: str
    filename: str
    chunk_count: int
    uploaded_at: datetime
    summary: str | None


async def get_cached_document_list(
    redis_client: redis.Redis, *, owner_id: str
) -> list[DocumentSummary] | None:
    raw = await redis_client.get(f"{_CACHE_KEY_PREFIX}{owner_id}")
    if raw is None:
        return None
    return [DocumentSummary.model_validate(item) for item in json.loads(raw)]


async def set_cached_document_list(
    redis_client: redis.Redis,
    *,
    owner_id: str,
    documents: list[DocumentSummary],
    ttl_seconds: int,
) -> None:
    payload = json.dumps([doc.model_dump(mode="json") for doc in documents])
    await redis_client.set(f"{_CACHE_KEY_PREFIX}{owner_id}", payload, ex=ttl_seconds)


async def invalidate_document_list_cache(redis_client: redis.Redis, *, owner_id: str) -> None:
    await redis_client.delete(f"{_CACHE_KEY_PREFIX}{owner_id}")
