"""Builds and compiles the LangGraph agent pipeline:

    START -> router -> (retrieval, tool -- whichever the Router selected,
             possibly both in parallel, possibly neither) -> END

The graph's job stops at "gather context" — it does not produce the final
answer. Composing that is the Summarizer's job (summarizer_agent.py), called
directly by each endpoint after the graph finishes: chat_routes.py (REST)
calls summarize(), chat_websocket.py calls stream_summary(). See
summarizer_agent.py's docstring for why the Summarizer isn't a graph node.

Each node appends to state["events"], so the graph's structure and the
"agent activity" panel's narrative are the same thing, not two things kept
in sync by hand — see agent_state.py.

Why LangGraph over just calling these functions in sequence from Python:
the routing is genuinely conditional (a "direct" question never touches
Qdrant or the MCP server at all), and expressing that as a graph with
conditional edges makes the control flow declarative and inspectable —
graph.get_graph().draw_mermaid() renders the actual decision structure,
which a chain of if/else branches buried in a function does not.
"""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.services.agent_router import route_after_router, router_node
from src.services.agent_state import AgentState
from src.services.retrieval_agent import retrieval_node
from src.services.tool_agent import tool_node


def build_agent_graph() -> CompiledStateGraph:
    builder = StateGraph(AgentState)

    builder.add_node("router", router_node)
    builder.add_node("retrieval", retrieval_node)
    builder.add_node("tool", tool_node)

    builder.add_edge(START, "router")
    builder.add_conditional_edges("router", route_after_router)
    builder.add_edge("retrieval", END)
    builder.add_edge("tool", END)

    return builder.compile()


# Compiled once at import time — building the graph is cheap and stateless,
# so there's no reason to repeat it on every request.
agent_graph = build_agent_graph()
