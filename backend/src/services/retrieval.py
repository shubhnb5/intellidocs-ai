"""Semantic search over stored document chunks: embed the question, ask
Qdrant for the nearest chunks by cosine similarity.

This is the "R" in RAG. It knows nothing about the LLM — see services/rag.py
for how retrieval and generation get combined.
"""

from pydantic import BaseModel
from qdrant_client.models import FieldCondition, Filter, MatchValue

from src.core.config import get_settings
from src.db.qdrant_client import get_qdrant_client
from src.services.embeddings import get_embedding_service


class RetrievedChunk(BaseModel):
    document_id: str
    filename: str
    chunk_index: int
    text: str
    score: float


def retrieve_relevant_chunks(
    question: str, *, top_k: int = 5, owner_id: str
) -> list[RetrievedChunk]:
    settings = get_settings()

    # Embedding the question with the *same* model used at ingestion is what
    # makes cosine similarity meaningful -- vectors from two different models
    # don't share a coordinate space.
    query_vector = get_embedding_service().embed([question])[0]

    # owner_id filter (Phase 8) keeps retrieval multi-tenant: one shared
    # Qdrant collection holds every user's chunks, so without this filter a
    # question would search across every document ever uploaded by anyone.
    owner_filter = Filter(
        must=[FieldCondition(key="owner_id", match=MatchValue(value=owner_id))]
    )

    results = get_qdrant_client().query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        query_filter=owner_filter,
        limit=top_k,
        with_payload=True,
    )

    chunks = []
    for point in results.points:
        payload = point.payload or {}
        chunks.append(
            RetrievedChunk(
                document_id=payload.get("document_id", ""),
                filename=payload.get("filename") or "untitled",
                chunk_index=payload.get("chunk_index", 0),
                text=payload.get("text", ""),
                score=point.score,
            )
        )
    return chunks
