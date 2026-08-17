from fastapi.testclient import TestClient

from main import app
from src.core.exceptions import LLMServiceError
from src.routes import chat_routes as chat_module
from src.services.agent_state import AgentEvent
from src.services.retrieval import RetrievedChunk

client = TestClient(app)


class _FakeGraph:
    """Stands in for the compiled LangGraph pipeline — the route only ever
    calls .ainvoke() on it, so that's the entire surface to fake."""

    def __init__(self, final_state: dict | None = None, *, raises: Exception | None = None):
        self._final_state = final_state
        self._raises = raises

    async def ainvoke(self, initial_state: dict) -> dict:
        if self._raises is not None:
            raise self._raises
        assert self._final_state is not None
        return self._final_state


def _context(**overrides) -> dict:
    base = {
        "route": "rag",
        "route_reasoning": "Question is about an uploaded report.",
        "retrieved_chunks": [
            RetrievedChunk(
                document_id="doc-1",
                filename="report.pdf",
                chunk_index=2,
                text="Revenue grew 12% year over year.",
                score=0.87,
            )
        ],
        "tool_results": [],
        "events": [
            AgentEvent(agent="router", message="Routed to 'rag'."),
            AgentEvent(agent="retrieval", message="Retrieved 1 chunk(s) from Qdrant."),
        ],
    }
    base.update(overrides)
    return base


def test_ask_question_returns_answer_with_sources_and_activity(monkeypatch, current_user):
    monkeypatch.setattr(chat_module, "agent_graph", _FakeGraph(_context()))

    async def fake_summarize(question, chunks, tool_results):
        return "The report shows 12% growth."

    monkeypatch.setattr(chat_module, "summarize", fake_summarize)

    response = client.post("/api/chat/ask", json={"question": "How much did revenue grow?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "The report shows 12% growth."
    assert body["route"] == "rag"
    assert body["sources"][0]["filename"] == "report.pdf"
    assert [event["agent"] for event in body["activity"]] == ["router", "retrieval"]


def test_ask_question_rejects_empty_question(current_user):
    response = client.post("/api/chat/ask", json={"question": ""})
    assert response.status_code == 422


def test_ask_question_requires_authentication():
    response = client.post("/api/chat/ask", json={"question": "anything?"})
    assert response.status_code == 401


def test_ask_question_surfaces_graph_errors(monkeypatch, current_user):
    monkeypatch.setattr(
        chat_module,
        "agent_graph",
        _FakeGraph(raises=LLMServiceError("The AI service is temporarily unavailable.")),
    )

    response = client.post("/api/chat/ask", json={"question": "anything?"})

    assert response.status_code == 502
    assert response.json()["error"]["type"] == "llm_service_error"


def test_ask_question_surfaces_summarizer_errors(monkeypatch, current_user):
    monkeypatch.setattr(chat_module, "agent_graph", _FakeGraph(_context()))

    async def failing_summarize(question, chunks, tool_results):
        raise LLMServiceError("The AI service is temporarily unavailable.")

    monkeypatch.setattr(chat_module, "summarize", failing_summarize)

    response = client.post("/api/chat/ask", json={"question": "anything?"})

    assert response.status_code == 502
    assert response.json()["error"]["type"] == "llm_service_error"
