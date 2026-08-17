from src.services import retrieval as retrieval_module


class _FakePoint:
    def __init__(self, payload: dict, score: float) -> None:
        self.payload = payload
        self.score = score


class _FakeQueryResponse:
    def __init__(self, points: list) -> None:
        self.points = points


class FakeEmbeddingService:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeQdrantClient:
    def __init__(self, points: list) -> None:
        self._points = points
        self.last_query_filter = None

    def query_points(self, collection_name, query, limit, with_payload, query_filter=None):
        self.last_query_filter = query_filter
        return _FakeQueryResponse(self._points[:limit])


def test_retrieve_relevant_chunks_maps_payload_to_model(monkeypatch):
    fake_points = [
        _FakePoint(
            {
                "document_id": "doc-1",
                "filename": "a.pdf",
                "chunk_index": 0,
                "text": "hello world",
            },
            score=0.9,
        )
    ]
    monkeypatch.setattr(
        retrieval_module, "get_embedding_service", lambda: FakeEmbeddingService()
    )
    fake_qdrant = FakeQdrantClient(fake_points)
    monkeypatch.setattr(retrieval_module, "get_qdrant_client", lambda: fake_qdrant)

    chunks = retrieval_module.retrieve_relevant_chunks(
        "what is this about?", top_k=3, owner_id="user-1"
    )

    assert len(chunks) == 1
    assert chunks[0].filename == "a.pdf"
    assert chunks[0].score == 0.9
    assert chunks[0].text == "hello world"
    # Retrieval is scoped to the asking user -- one shared Qdrant collection
    # holds every user's chunks (see retrieval.py), so a query without this
    # filter would search across everyone's documents.
    assert fake_qdrant.last_query_filter is not None


def test_retrieve_relevant_chunks_returns_empty_list_when_no_matches(monkeypatch):
    monkeypatch.setattr(
        retrieval_module, "get_embedding_service", lambda: FakeEmbeddingService()
    )
    monkeypatch.setattr(retrieval_module, "get_qdrant_client", lambda: FakeQdrantClient([]))

    assert retrieval_module.retrieve_relevant_chunks("anything", owner_id="user-1") == []
