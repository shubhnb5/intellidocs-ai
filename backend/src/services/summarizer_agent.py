"""Summarizer/Report Agent: composes the final grounded answer from whatever
the Retrieval and Tool agents found in the graph (see agent_graph.py) — it never
talks to Qdrant or the MCP server directly, only the context they gathered.

Unlike the other three agents, this one is not a LangGraph node. LangGraph's
node model doesn't cleanly support streaming partial tokens back out to an
external consumer (the WebSocket) without extra custom-streaming plumbing,
so the graph's job ends at "gather context" (see agent_graph.py) and this module
is called directly afterward: summarize() for the REST endpoint,
stream_summary() for the WebSocket. Both share the same prompt and
context-building logic below — the only difference is streamed vs. not.
"""

from collections.abc import AsyncIterator

from src.services.llm import ask_claude, stream_claude
from src.services.mcp_client import ToolCallResult
from src.services.retrieval import RetrievedChunk

SUMMARIZER_SYSTEM_PROMPT = (
    "You are IntelliDocs AI, a research assistant. Compose a final answer "
    "to the user's question using ONLY the document excerpts and tool "
    "results provided below. Cite document excerpts inline as [n], "
    "matching their numbers. Reference tool results by name when you use "
    "them. If neither source contains enough information, say so plainly "
    "instead of guessing — never fabricate an answer."
)


def _build_user_message(
    question: str, chunks: list[RetrievedChunk], tool_results: list[ToolCallResult]
) -> str:
    parts: list[str] = []

    if chunks:
        excerpts = "\n\n".join(
            f"[{index + 1}] (from {chunk.filename}) {chunk.text}"
            for index, chunk in enumerate(chunks)
        )
        parts.append(f"Document excerpts:\n\n{excerpts}")

    if tool_results:
        tool_text = "\n\n".join(
            f"Tool '{result.tool_name}' result:\n{result.output}" for result in tool_results
        )
        parts.append(f"Tool results:\n\n{tool_text}")

    if not parts:
        parts.append(
            "(No document excerpts or tool results were retrieved for this question — "
            "the Router judged this answerable from general knowledge, or nothing "
            "relevant was found.)"
        )

    parts.append(f"Question: {question}")
    return "\n\n".join(parts)


async def summarize(
    question: str, chunks: list[RetrievedChunk], tool_results: list[ToolCallResult]
) -> str:
    """Non-streaming: the REST endpoint's shape (Phase 3/6) — one complete
    answer in the response body."""
    return await ask_claude(
        system=SUMMARIZER_SYSTEM_PROMPT,
        user_message=_build_user_message(question, chunks, tool_results),
    )


async def stream_summary(
    question: str, chunks: list[RetrievedChunk], tool_results: list[ToolCallResult]
) -> AsyncIterator[str]:
    """Streaming: the WebSocket endpoint's shape (Phase 7) — text deltas as
    Claude generates them, so the frontend can render the answer live."""
    async for text_delta in stream_claude(
        system=SUMMARIZER_SYSTEM_PROMPT,
        user_message=_build_user_message(question, chunks, tool_results),
    ):
        yield text_delta
