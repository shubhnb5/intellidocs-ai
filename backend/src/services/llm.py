"""Wraps the Anthropic SDK — the one place in the codebase that knows about
timeouts, retries, model choice, and cost logging. Route/agent code never
imports `anthropic` directly; it calls the ask_* functions here, so swapping
models (or providers) touches this file only.

Async throughout (AsyncAnthropic, not the sync client): every one of these
functions is called from a LangGraph agent node running inside an async
FastAPI request (see agent_graph.py), and a blocking network call there
would stall the event loop for every other concurrent request, not just the
one that made it. This is a deliberate change from Phase 3, which used the
sync client — fine then, when the only caller was a single request handler
with no other async work happening alongside it.
"""

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import TypeVar

import anthropic
from loguru import logger
from pydantic import BaseModel

from src.core.config import get_settings
from src.core.exceptions import LLMNotConfiguredError, LLMServiceError

# Anthropic list pricing, USD per million tokens. Used only to log an
# approximate cost per call below -- nothing here is billed against this
# table, so a stale price is a logging inaccuracy, not a financial bug.
# Check https://platform.claude.com/docs/en/pricing if these drift.
_PRICING_PER_MTOK = {
    "claude-sonnet-5": {"input": 3.00, "output": 15.00},
    "claude-opus-5": {"input": 5.00, "output": 25.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}

_StructuredOutputT = TypeVar("_StructuredOutputT", bound=BaseModel)


@lru_cache
def get_claude_client() -> anthropic.AsyncAnthropic:
    settings = get_settings()
    return anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.claude_timeout_seconds,
        # The SDK retries 429/408/409/5xx with exponential backoff itself --
        # no custom retry loop needed unless we outgrow this.
        max_retries=settings.claude_max_retries,
    )


def _require_configured() -> None:
    if not get_settings().anthropic_api_key:
        raise LLMNotConfiguredError(
            "ANTHROPIC_API_KEY is not set. Add it to backend/.env."
        )


def _estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    rates = _PRICING_PER_MTOK.get(model)
    if rates is None:
        return None
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000


def _log_usage(model: str, usage) -> None:
    cost = _estimate_cost_usd(model, usage.input_tokens, usage.output_tokens)
    logger.info(
        "claude call model={} input_tokens={} output_tokens={} est_cost_usd={}",
        model,
        usage.input_tokens,
        usage.output_tokens,
        f"{cost:.5f}" if cost is not None else "unknown",
    )


async def ask_claude(*, system: str, user_message: str) -> str:
    """Single non-streaming completion, plain text in and out. Used by the
    Summarizer agent — deliberately the simplest call shape here; streaming
    arrives in Phase 7 alongside the WebSocket chat endpoint.
    """
    _require_configured()
    settings = get_settings()
    client = get_claude_client()

    try:
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            system=system,
            output_config={"effort": settings.claude_effort},
            messages=[{"role": "user", "content": user_message}],
        )
    except anthropic.APIError as exc:
        logger.error("Claude API call failed: {}", exc)
        raise LLMServiceError("The AI service is temporarily unavailable.") from exc

    if response.stop_reason == "refusal":
        raise LLMServiceError("Claude declined to answer this request.")

    _log_usage(settings.anthropic_model, response.usage)
    return "\n".join(block.text for block in response.content if block.type == "text")


async def stream_claude(*, system: str, user_message: str) -> AsyncIterator[str]:
    """Streaming variant of ask_claude() — yields text deltas as they arrive
    instead of returning the complete response in one piece. Used by the
    Summarizer agent's WebSocket path (see services/summarizer_agent.py)
    so the frontend can render the answer as it's generated, the same way
    Claude's own chat UI does, instead of waiting for the full response.
    """
    _require_configured()
    settings = get_settings()
    client = get_claude_client()

    try:
        async with client.messages.stream(
            model=settings.anthropic_model,
            max_tokens=1024,
            system=system,
            output_config={"effort": settings.claude_effort},
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            async for text in stream.text_stream:
                yield text
            final_message = await stream.get_final_message()
    except anthropic.APIError as exc:
        logger.error("Claude streaming call failed: {}", exc)
        raise LLMServiceError("The AI service is temporarily unavailable.") from exc

    if final_message.stop_reason == "refusal":
        raise LLMServiceError("Claude declined to answer this request.")

    _log_usage(settings.anthropic_model, final_message.usage)


async def ask_claude_structured(
    *, system: str, user_message: str, output_model: type[_StructuredOutputT]
) -> _StructuredOutputT:
    """Ask Claude for a response validated against a Pydantic model. Used by
    the Router agent, whose whole job is producing one reliable enum
    decision rather than free text a caller then has to parse.
    """
    _require_configured()
    settings = get_settings()
    client = get_claude_client()

    try:
        response = await client.messages.parse(
            model=settings.anthropic_model,
            max_tokens=500,
            system=system,
            output_config={"effort": settings.claude_effort},
            messages=[{"role": "user", "content": user_message}],
            output_format=output_model,
        )
    except anthropic.APIError as exc:
        logger.error("Claude structured-output call failed: {}", exc)
        raise LLMServiceError("The AI service is temporarily unavailable.") from exc

    _log_usage(settings.anthropic_model, response.usage)
    if response.parsed_output is None:
        raise LLMServiceError("Claude did not return a valid structured response.")
    return response.parsed_output


class ToolUseRequest(BaseModel):
    id: str
    name: str
    input: dict


async def ask_claude_for_tool_calls(
    *, system: str, user_message: str, tools: list[dict]
) -> list[ToolUseRequest]:
    """Ask Claude which of the given tools to call. Forces at least one tool
    call (tool_choice: any) — this is only invoked by the Tool agent after
    the Router has already decided tools are needed, so a plain-text
    non-answer isn't a useful outcome here.
    """
    _require_configured()
    settings = get_settings()
    client = get_claude_client()

    try:
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            system=system,
            tools=tools,
            tool_choice={"type": "any"},
            output_config={"effort": settings.claude_effort},
            messages=[{"role": "user", "content": user_message}],
        )
    except anthropic.APIError as exc:
        logger.error("Claude tool-selection call failed: {}", exc)
        raise LLMServiceError("The AI service is temporarily unavailable.") from exc

    _log_usage(settings.anthropic_model, response.usage)
    return [
        ToolUseRequest(id=block.id, name=block.name, input=block.input)
        for block in response.content
        if block.type == "tool_use"
    ]
