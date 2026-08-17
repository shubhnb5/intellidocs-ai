"""End-to-end tests of the compiled LangGraph pipeline: given a route, does
the graph actually execute the nodes it should (and only those), with state
flowing through correctly? The graph's job stops at "gather context" — it
does not produce an answer (see agent_graph.py / summarizer_agent.py
docstrings) — so these tests check route/retrieved_chunks/tool_results/events,
not an answer field. Every external call (Claude, Qdrant, MCP) is faked at
the boundary the corresponding agent module imports it through — see the
per-agent test files for unit-level coverage of each node alone.
"""

from src.services import retrieval_agent as retrieval_agent_module
from src.services import agent_router as router_module
from src.services import tool_agent as tool_agent_module
from src.services.agent_graph import agent_graph
from src.services.agent_router import RouteDecision
from src.services.mcp_client import ToolCallResult
from src.services.retrieval import RetrievedChunk


def _initial_state(question: str) -> dict:
    return {
        "question": question,
        "top_k": 5,
        "user_id": "test-user-id",
        "route": "",
        "route_reasoning": "",
        "retrieved_chunks": [],
        "tool_results": [],
        "events": [],
    }


def _patch_router(monkeypatch, route: str) -> None:
    async def fake(*, system, user_message, output_model):
        return RouteDecision(route=route, reasoning=f"test forced route={route}")

    monkeypatch.setattr(router_module, "ask_claude_structured", fake)


async def test_direct_route_runs_only_the_router(monkeypatch):
    _patch_router(monkeypatch, "direct")

    final_state = await agent_graph.ainvoke(_initial_state("What is the capital of France?"))

    assert final_state["route"] == "direct"
    assert final_state["retrieved_chunks"] == []
    assert final_state["tool_results"] == []
    assert {event.agent for event in final_state["events"]} == {"router"}


async def test_rag_route_runs_retrieval_only(monkeypatch):
    _patch_router(monkeypatch, "rag")
    chunks = [
        RetrievedChunk(document_id="d1", filename="a.pdf", chunk_index=0, text="hi", score=0.9)
    ]
    monkeypatch.setattr(
        retrieval_agent_module,
        "retrieve_relevant_chunks",
        lambda question, top_k, owner_id: chunks,
    )

    final_state = await agent_graph.ainvoke(_initial_state("What does the doc say?"))

    assert final_state["route"] == "rag"
    assert final_state["retrieved_chunks"] == chunks
    assert final_state["tool_results"] == []
    assert {event.agent for event in final_state["events"]} == {"router", "retrieval"}


async def test_tools_route_runs_tool_only(monkeypatch):
    _patch_router(monkeypatch, "tools")

    async def fake_call_mcp_tools(question: str):
        return []

    monkeypatch.setattr(tool_agent_module, "call_mcp_tools", fake_call_mcp_tools)

    final_state = await agent_graph.ainvoke(_initial_state("What's today's weather?"))

    assert final_state["route"] == "tools"
    assert final_state["retrieved_chunks"] == []
    assert {event.agent for event in final_state["events"]} == {"router", "tool"}


async def test_both_route_runs_retrieval_and_tool(monkeypatch):
    _patch_router(monkeypatch, "both")
    chunks = [
        RetrievedChunk(document_id="d1", filename="a.pdf", chunk_index=0, text="hi", score=0.9)
    ]
    tool_results = [
        ToolCallResult(
            tool_name="calculate", tool_input={"expression": "1+1"}, output="2", is_error=False
        )
    ]
    monkeypatch.setattr(
        retrieval_agent_module,
        "retrieve_relevant_chunks",
        lambda question, top_k, owner_id: chunks,
    )

    async def fake_call_mcp_tools(question: str):
        return tool_results

    monkeypatch.setattr(tool_agent_module, "call_mcp_tools", fake_call_mcp_tools)

    final_state = await agent_graph.ainvoke(_initial_state("What does the doc say, and 1+1?"))

    assert final_state["route"] == "both"
    assert final_state["retrieved_chunks"] == chunks
    assert final_state["tool_results"] == tool_results
    # Retrieval and tool run in the same LangGraph superstep on "both" --
    # this also proves the events reducer merges their parallel writes
    # instead of one clobbering the other (see agent_state.py).
    assert {event.agent for event in final_state["events"]} == {"router", "retrieval", "tool"}
    assert len(final_state["events"]) == 3
