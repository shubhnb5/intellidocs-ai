from src.services import retrieval_agent as retrieval_agent_module
from src.services.retrieval import RetrievedChunk


async def test_retrieval_node_returns_chunks_and_event(monkeypatch):
    chunks = [
        RetrievedChunk(
            document_id="doc-1", filename="a.pdf", chunk_index=0, text="hello", score=0.9
        )
    ]
    monkeypatch.setattr(
        retrieval_agent_module,
        "retrieve_relevant_chunks",
        lambda question, top_k, owner_id: chunks,
    )

    result = await retrieval_agent_module.retrieval_node(
        {"question": "hi?", "top_k": 5, "user_id": "test-user-id"}
    )

    assert result["retrieved_chunks"] == chunks
    assert len(result["events"]) == 1
    assert result["events"][0].agent == "retrieval"
    assert "1 chunk" in result["events"][0].message


async def test_retrieval_node_handles_no_matches(monkeypatch):
    monkeypatch.setattr(
        retrieval_agent_module,
        "retrieve_relevant_chunks",
        lambda question, top_k, owner_id: [],
    )

    result = await retrieval_agent_module.retrieval_node(
        {"question": "hi?", "top_k": 5, "user_id": "test-user-id"}
    )

    assert result["retrieved_chunks"] == []
    assert "0 chunk" in result["events"][0].message
