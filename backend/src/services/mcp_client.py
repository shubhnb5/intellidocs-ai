"""Bridges the Tool Agent to the MCP server (Phase 5): discovers its tools,
lets Claude decide which to call, and executes them against the real server
over HTTP.

Connects fresh per call rather than holding a persistent connection — at
this project's request volume that's simpler and avoids managing connection
lifecycle across FastAPI requests. A production system handling much higher
throughput would pool this instead.
"""

from loguru import logger
from mcp import Client
from pydantic import BaseModel

from src.core.config import get_settings
from src.core.exceptions import LLMNotConfiguredError, LLMServiceError, MCPServiceError
from src.services.llm import ask_claude_for_tool_calls

TOOL_SELECTION_SYSTEM_PROMPT = (
    "You are the Tool Agent for IntelliDocs AI. Call whichever of the "
    "available tools are needed to answer the user's question with current "
    "or computed information. You may call more than one tool."
)


class ToolCallResult(BaseModel):
    tool_name: str
    tool_input: dict
    output: str
    is_error: bool


async def call_mcp_tools(question: str) -> list[ToolCallResult]:
    """The Tool agent's entire job: decide which MCP tool(s) to use, and run
    them. Turning the results into a final answer is the Summarizer's job,
    not this function's — it returns raw tool output.
    """
    settings = get_settings()
    mcp_url = f"{settings.mcp_server_url}/mcp"

    try:
        async with Client(mcp_url) as client:
            tools_result = await client.list_tools()
            claude_tools = [
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.input_schema,
                }
                for tool in tools_result.tools
            ]

            tool_uses = await ask_claude_for_tool_calls(
                system=TOOL_SELECTION_SYSTEM_PROMPT,
                user_message=question,
                tools=claude_tools,
            )

            results: list[ToolCallResult] = []
            for tool_use in tool_uses:
                call_result = await client.call_tool(tool_use.name, tool_use.input)
                output_text = "\n".join(
                    block.text for block in call_result.content if block.type == "text"
                )
                results.append(
                    ToolCallResult(
                        tool_name=tool_use.name,
                        tool_input=tool_use.input,
                        output=output_text,
                        is_error=call_result.is_error,
                    )
                )
            return results
    except (LLMNotConfiguredError, LLMServiceError):
        raise  # already a clean AppError -- don't wrap it in a second one
    except Exception as exc:
        logger.error("MCP tool call failed: {}", exc)
        raise MCPServiceError(f"Could not reach the MCP tool server: {exc}") from exc
