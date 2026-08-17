"""Retrieval Agent: pulls relevant chunks from Qdrant when the Router says
the question needs document content. A thin wrapper — the retrieval logic
itself lives in services/retrieval.py (Phase 3), unchanged; this just
adapts it to the graph's node signature and emits an activity event.
"""

from src.services.agent_state import AgentEvent, AgentState
from src.services.retrieval import retrieve_relevant_chunks


async def retrieval_node(state: AgentState) -> dict:
    chunks = retrieve_relevant_chunks(
        state["question"], top_k=state["top_k"], owner_id=state["user_id"]
    )
    return {
        "retrieved_chunks": chunks,
        "events": [
            AgentEvent(
                agent="retrieval",
                message=f"Retrieved {len(chunks)} chunk(s) from Qdrant.",
            )
        ],
    }
