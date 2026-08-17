"""Multi-agent RAG Q&A: REST endpoint (this file) and WebSocket endpoint
(chat_websocket.py) share the same pipeline — the agent graph gathers context
(Router decides, Retrieval/Tool fetch it), then the Summarizer composes the
answer. This endpoint waits for the complete answer and returns it in one
response; the WebSocket streams both the agent activity and the answer live
as they happen. See services/agent_graph.py and services/summarizer_agent.py.

Same URL as Phase 3's original plain-RAG endpoint — the agent pipeline
replaced that endpoint's internals, not its contract.
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.core.auth_dependency import CurrentUser, get_current_user
from src.core.config import get_settings
from src.core.rate_limit import RateLimiter
from src.services.agent_graph import agent_graph
from src.services.agent_state import AgentState
from src.services.summarizer_agent import summarize

router = APIRouter()

_settings = get_settings()
_ask_rate_limiter = RateLimiter(
    limit=_settings.rate_limit_requests,
    window_seconds=_settings.rate_limit_window_seconds,
    scope="chat_ask",
)


# --- request/response schemas -----------------------------------------


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class SourceChunk(BaseModel):
    filename: str
    chunk_index: int
    text: str
    score: float


class AgentActivity(BaseModel):
    """One entry in the Router/Retrieval/Tool/Summarizer trace — what the
    frontend's agent activity panel (Phase 7) renders."""

    agent: str
    message: str
    timestamp: datetime


class AskResponse(BaseModel):
    answer: str
    route: str
    route_reasoning: str
    sources: list[SourceChunk]
    activity: list[AgentActivity]


# --- routes --------------------------------------------------------------


@router.post(
    "/api/chat/ask",
    response_model=AskResponse,
    tags=["Chat"],
    summary="Ask a question, routed through the Router/Retrieval/Tool/Summarizer agents",
    description=(
        "The Router agent decides whether to retrieve documents (Qdrant), "
        "call MCP tools (web search, calculator, document metadata), both, "
        "or neither. The Summarizer agent then composes a grounded final "
        "answer from whatever was gathered. For a live, streaming version "
        "of this same pipeline, use the /ws/chat WebSocket instead."
    ),
    dependencies=[Depends(_ask_rate_limiter)],
)
async def ask_question(
    request: AskRequest, current_user: CurrentUser = Depends(get_current_user)
) -> AskResponse:
    initial_state: AgentState = {
        "question": request.question,
        "top_k": request.top_k,
        "user_id": current_user.user_id,
        "route": "",
        "route_reasoning": "",
        "retrieved_chunks": [],
        "tool_results": [],
        "events": [],
    }

    context = await agent_graph.ainvoke(initial_state)
    answer = await summarize(
        request.question, context["retrieved_chunks"], context["tool_results"]
    )

    return AskResponse(
        answer=answer,
        route=context["route"],
        route_reasoning=context["route_reasoning"],
        sources=[
            SourceChunk(
                filename=chunk.filename,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                score=chunk.score,
            )
            for chunk in context["retrieved_chunks"]
        ],
        activity=[
            AgentActivity(agent=event.agent, message=event.message, timestamp=event.timestamp)
            for event in context["events"]
        ],
    )
