"""Shared state passed between LangGraph nodes.

The graph's job stops at "gather context" — route + retrieved_chunks +
tool_results. There's no `answer` field: composing the final answer is the
Summarizer's job (services/summarizer_agent.py), called directly
after the graph finishes rather than as a graph node — see that module's
docstring for why.

`events` is what powers the "agent activity" panel, streamed live over
WebSocket (Phase 7) and also returned in full by the REST endpoint. It uses
`Annotated[list[AgentEvent], operator.add]` because the Retrieval and Tool
agents can run in the same LangGraph superstep (parallel, on the "both"
route) and each appends its own event — the reducer concatenates their
partial updates instead of one overwriting the other. `retrieved_chunks` and
`tool_results` don't need a reducer: each has exactly one writer, so plain
last-write-wins is correct and simpler.
"""

import operator
from datetime import UTC, datetime
from typing import Annotated, TypedDict

from pydantic import BaseModel, Field

from src.services.mcp_client import ToolCallResult
from src.services.retrieval import RetrievedChunk


class AgentEvent(BaseModel):
    agent: str
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentState(TypedDict):
    question: str
    top_k: int
    user_id: str
    route: str
    route_reasoning: str
    retrieved_chunks: list[RetrievedChunk]
    tool_results: list[ToolCallResult]
    events: Annotated[list[AgentEvent], operator.add]
