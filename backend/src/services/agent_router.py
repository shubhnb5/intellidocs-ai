"""Router Agent: the first stop for every question. Decides whether
answering it needs the uploaded documents (RAG), live MCP tools, both, or
neither — every other agent's involvement is conditional on this decision.
"""

from typing import Literal

from langgraph.graph import END
from pydantic import BaseModel

from src.services.agent_state import AgentEvent, AgentState
from src.services.llm import ask_claude_structured

ROUTER_SYSTEM_PROMPT = (
    "You are the Router for IntelliDocs AI, a document research copilot. "
    "Given a user's question, decide how it should be answered:\n\n"
    '- "rag": the question is about the content of documents the user has '
    "uploaded.\n"
    '- "tools": the question needs live/current information (web search) '
    "or a calculation, not document content.\n"
    '- "both": the question needs document content AND live information '
    "or computation.\n"
    '- "direct": general knowledge or conversational — answer from your '
    "own knowledge, no documents or tools needed.\n\n"
    "Respond with the route and a one-sentence reason."
)


class RouteDecision(BaseModel):
    route: Literal["rag", "tools", "both", "direct"]
    reasoning: str


async def router_node(state: AgentState) -> dict:
    decision = await ask_claude_structured(
        system=ROUTER_SYSTEM_PROMPT,
        user_message=state["question"],
        output_model=RouteDecision,
    )
    return {
        "route": decision.route,
        "route_reasoning": decision.reasoning,
        "events": [
            AgentEvent(
                agent="router",
                message=f"Routed to '{decision.route}': {decision.reasoning}",
            )
        ],
    }


def route_after_router(state: AgentState) -> list[str]:
    """The conditional edge out of "router" — returns the actual node
    name(s) to run next. A list of two names ("both") fans out to both
    nodes in the same LangGraph superstep; a list of one runs just that
    node; "direct" needs neither, so the graph ends immediately — the
    Summarizer still runs, just outside the graph (see agent_graph.py).
    """
    route = state["route"]
    if route == "both":
        return ["retrieval", "tool"]
    if route == "rag":
        return ["retrieval"]
    if route == "tools":
        return ["tool"]
    return [END]
