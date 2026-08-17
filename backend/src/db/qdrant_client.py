"""Qdrant connection + collection lifecycle.

One collection holds every document's chunks for now — there's no per-user
isolation yet. That's a Phase 8 concern: once auth exists, uploads get a
user_id in the payload and retrieval filters on it.
"""

from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from src.core.config import get_settings


@lru_cache
def get_qdrant_client() -> QdrantClient:
    """Cached so every request/service reuses one connection instead of
    opening a new one per call."""
    settings = get_settings()
    return QdrantClient(url=settings.qdrant_url)


def ensure_collection() -> None:
    """Create the chunks collection if it doesn't exist yet.

    Called once at startup (see main.py's lifespan) so the first upload never
    races a missing collection.
    """
    settings = get_settings()
    client = get_qdrant_client()
    if client.collection_exists(settings.qdrant_collection):
        return
    client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=VectorParams(size=settings.embedding_dim, distance=Distance.COSINE),
    )
