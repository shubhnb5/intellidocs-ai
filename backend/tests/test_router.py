from langgraph.graph import END

from src.services import agent_router as router_module
from src.services.agent_router import RouteDecision, route_after_router


def test_route_after_router_fans_out_for_both():
    assert route_after_router({"route": "both"}) == ["retrieval", "tool"]


def test_route_after_router_selects_retrieval_only_for_rag():
    assert route_after_router({"route": "rag"}) == ["retrieval"]


def test_route_after_router_selects_tool_only_for_tools():
    assert route_after_router({"route": "tools"}) == ["tool"]


def test_route_after_router_ends_the_graph_for_direct():
    # The Summarizer still runs for "direct" -- just outside the graph, see
    # agent_graph.py and summarizer_agent.py.
    assert route_after_router({"route": "direct"}) == [END]


async def test_router_node_records_decision_and_event(monkeypatch):
    decision = RouteDecision(route="rag", reasoning="Asks about an uploaded report.")

    async def fake_ask_claude_structured(*, system, user_message, output_model):
        return decision

    monkeypatch.setattr(router_module, "ask_claude_structured", fake_ask_claude_structured)

    result = await router_module.router_node({"question": "What does the report say?"})

    assert result["route"] == "rag"
    assert result["route_reasoning"] == "Asks about an uploaded report."
    assert len(result["events"]) == 1
    assert result["events"][0].agent == "router"
