"""Tests the WebSocket chat endpoint's wire protocol end-to-end against a
fake streaming graph and a fake stream_summary — no real Claude, Qdrant, or
MCP server needed.

Auth (Phase 8): resolve_user_from_token is a plain function the handler
calls manually (not a raising Depends), specifically so it can control the
accept-then-close-with-a-custom-code behavior on failure -- see
chat_websocket.py's module docstring. That means it isn't overridable through
app.dependency_overrides like get_current_user is; tests that aren't about
auth itself fake it directly via monkeypatch, same as agent_graph below.
The dedicated auth tests at the bottom use the real function instead.
"""

from fastapi.testclient import TestClient

from main import app
from src.core.auth_dependency import CurrentUser
from src.core.exceptions import LLMServiceError
from src.routes import chat_websocket as websocket_module
from src.services.agent_state import AgentEvent
from src.services.retrieval import RetrievedChunk

client = TestClient(app)

_TEST_USER = CurrentUser(user_id="test-user-id", email="test@example.com")


def _fake_resolve_user(token: str, db) -> CurrentUser:
    return _TEST_USER


def _patch_auth(monkeypatch) -> None:
    monkeypatch.setattr(websocket_module, "resolve_user_from_token", _fake_resolve_user)


class _FakeStreamingGraph:
    """Stands in for the compiled graph — the WS handler only ever calls
    .astream(), so that's the entire surface to fake."""

    def __init__(self, updates: list[dict]) -> None:
        self._updates = updates

    async def astream(self, initial_state, stream_mode="updates"):
        for update in self._updates:
            yield update


class _RaisingGraph:
    """Simulates a failure inside the graph itself (e.g. Claude/Qdrant
    unreachable). `yield` after `raise` is unreachable but still makes this
    a valid async *generator* function -- matching astream()'s real shape,
    so the failure surfaces exactly where it would in production: on the
    handler's first `async for` iteration."""

    async def astream(self, initial_state, stream_mode="updates"):
        raise LLMServiceError("The AI service is temporarily unavailable.")
        yield  # pragma: no cover


def test_websocket_streams_activity_then_answer_then_done(monkeypatch, db_session):
    _patch_auth(monkeypatch)
    chunk = RetrievedChunk(
        document_id="doc-1",
        filename="report.pdf",
        chunk_index=0,
        text="Revenue grew 12%.",
        score=0.9,
    )
    updates = [
        {
            "router": {
                "route": "rag",
                "route_reasoning": "About an uploaded report.",
                "events": [AgentEvent(agent="router", message="Routed to 'rag'.")],
            }
        },
        {
            "retrieval": {
                "retrieved_chunks": [chunk],
                "events": [AgentEvent(agent="retrieval", message="Retrieved 1 chunk(s).")],
            }
        },
    ]
    monkeypatch.setattr(websocket_module, "agent_graph", _FakeStreamingGraph(updates))

    async def fake_stream_summary(question, chunks, tool_results):
        for delta in ["Revenue ", "grew 12%."]:
            yield delta

    monkeypatch.setattr(websocket_module, "stream_summary", fake_stream_summary)

    with client.websocket_connect("/ws/chat?token=fake-token") as ws:
        ws.send_json({"type": "ask", "question": "How much did revenue grow?"})

        first = ws.receive_json()
        assert first["type"] == "agent_activity"
        assert first["agent"] == "router"
        assert first["message"] == "Routed to 'rag'."
        assert "timestamp" in first

        second = ws.receive_json()
        assert second["agent"] == "retrieval"

        third = ws.receive_json()
        assert third["type"] == "agent_activity"
        assert third["agent"] == "summarizer"

        assert ws.receive_json() == {"type": "answer_chunk", "text": "Revenue "}
        assert ws.receive_json() == {"type": "answer_chunk", "text": "grew 12%."}

        done = ws.receive_json()
        assert done["type"] == "done"
        assert done["route"] == "rag"
        assert done["sources"][0]["filename"] == "report.pdf"


def test_websocket_rejects_invalid_message(monkeypatch, db_session):
    _patch_auth(monkeypatch)
    monkeypatch.setattr(websocket_module, "agent_graph", _FakeStreamingGraph([]))

    with client.websocket_connect("/ws/chat?token=fake-token") as ws:
        ws.send_json({"type": "ask", "question": ""})  # fails AskRequest's min_length

        response = ws.receive_json()
        assert response["type"] == "error"


def test_websocket_reports_errors_and_keeps_connection_open(monkeypatch, db_session):
    _patch_auth(monkeypatch)
    monkeypatch.setattr(websocket_module, "agent_graph", _RaisingGraph())

    with client.websocket_connect("/ws/chat?token=fake-token") as ws:
        ws.send_json({"type": "ask", "question": "anything?"})

        response = ws.receive_json()
        assert response == {
            "type": "error",
            "message": "The AI service is temporarily unavailable.",
        }

        # The connection survived the error -- prove it by sending again.
        ws.send_json({"type": "ask", "question": "anything?"})
        response_again = ws.receive_json()
        assert response_again["type"] == "error"


def test_websocket_closes_with_4401_when_token_is_missing(db_session):
    with client.websocket_connect("/ws/chat") as ws:
        response = ws.receive()

    assert response["type"] == "websocket.close"
    assert response["code"] == websocket_module.AUTH_FAILURE_CLOSE_CODE


def test_websocket_closes_with_4401_when_token_is_invalid(db_session):
    with client.websocket_connect("/ws/chat?token=not-a-real-token") as ws:
        response = ws.receive()

    assert response["type"] == "websocket.close"
    assert response["code"] == websocket_module.AUTH_FAILURE_CLOSE_CODE
