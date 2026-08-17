"""Turns text chunks into vectors for storage/search in Qdrant.

Local embeddings (ONNX, via fastembed) rather than a hosted API: ingestion
can embed hundreds of chunks per document with no network round-trip, no
per-token cost, and no risk of an upload failing because an external
embeddings API is rate-limited or down. fastembed is Qdrant's own lightweight
embedding library — no PyTorch dependency, small Docker image, fast cold
start.

Swapping to a hosted provider (Voyage AI, OpenAI) later means changing this
one file; nothing else in the codebase knows or cares how embeddings are
produced.
"""

from functools import lru_cache

from fastembed import TextEmbedding

from src.core.config import get_settings


class EmbeddingService:
    def __init__(self, model_name: str) -> None:
        self._model = TextEmbedding(model_name=model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(texts)]


@lru_cache
def get_embedding_service() -> EmbeddingService:
    """Cached: loading the ONNX model is the expensive part, so do it once
    per process, not once per request."""
    settings = get_settings()
    return EmbeddingService(settings.embedding_model)
