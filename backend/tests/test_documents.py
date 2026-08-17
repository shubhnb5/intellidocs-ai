"""Tests the upload/list/detail route logic against fake embedding, Qdrant,
and NLP services plus an in-memory SQLite DB (see conftest.py) — no real
Qdrant instance, spaCy model, or model download required, so these stay fast
and hermetic enough to run in CI on every push.

Auth (Phase 8): every route here requires a logged-in user, so fake_pipeline
also pulls in the `current_user` fixture (see conftest.py), which overrides
get_current_user/get_current_user_or_internal for the whole test regardless
of what's in the request — these tests are about upload/list/detail logic,
not auth itself (see test_auth_routes.py for that).
"""

import io

import pytest
from docx import Document
from fastapi.testclient import TestClient

from main import app
from src.routes import document_routes as documents_module
from src.services.nlp import Entity, NlpResult

client = TestClient(app)


class FakeEmbeddingService:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeQdrantClient:
    def __init__(self) -> None:
        self.points: list = []

    def upsert(self, collection_name: str, points: list) -> None:
        self.points.extend(points)


_FAKE_NLP_RESULT = NlpResult(
    entities=[Entity(text="Anthropic", label="ORG")],
    topics=["multi-agent rag copilot"],
    summary="IntelliDocs AI is a multi-agent RAG copilot.",
)


@pytest.fixture
def fake_pipeline(monkeypatch, db_session, current_user):
    fake_qdrant = FakeQdrantClient()
    monkeypatch.setattr(
        documents_module, "get_embedding_service", lambda: FakeEmbeddingService()
    )
    monkeypatch.setattr(documents_module, "get_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(documents_module, "analyze_document", lambda text: _FAKE_NLP_RESULT)
    return fake_qdrant


def _sample_docx_bytes(text: str) -> bytes:
    buffer = io.BytesIO()
    doc = Document()
    doc.add_paragraph(text)
    doc.save(buffer)
    return buffer.getvalue()


def _upload(filename: str, text: str):
    return client.post(
        "/api/documents/upload",
        files={
            "file": (
                filename,
                _sample_docx_bytes(text),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )


def test_upload_docx_returns_chunk_count_and_nlp_fields(fake_pipeline):
    response = _upload("sample.docx", "IntelliDocs AI is a multi-agent RAG copilot. " * 50)

    assert response.status_code == 201
    body = response.json()
    assert body["chunk_count"] > 0
    assert body["filename"] == "sample.docx"
    assert body["summary"] == _FAKE_NLP_RESULT.summary
    assert body["entities"] == [{"text": "Anthropic", "label": "ORG"}]
    assert body["topics"] == ["multi-agent rag copilot"]
    assert len(fake_pipeline.points) == body["chunk_count"]


def test_upload_rejects_unsupported_file_type(fake_pipeline):
    response = client.post(
        "/api/documents/upload",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["type"] == "unsupported_file_type"
    assert fake_pipeline.points == []


def test_list_documents_after_upload(fake_pipeline):
    _upload("list-test.docx", "Short document.")

    response = client.get("/api/documents")

    assert response.status_code == 200
    filenames = [d["filename"] for d in response.json()["documents"]]
    assert "list-test.docx" in filenames


def test_get_document_returns_full_detail(fake_pipeline):
    document_id = _upload("detail-test.docx", "Short document.").json()["document_id"]

    response = client.get(f"/api/documents/{document_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "detail-test.docx"
    assert body["entities"] == [{"text": "Anthropic", "label": "ORG"}]


def test_get_document_returns_404_for_unknown_id(fake_pipeline):
    response = client.get("/api/documents/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["type"] == "document_not_found"
