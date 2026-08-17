"""Tests call_mcp_tools against a fake MCP Client — no real MCP server
needs to be running for these to pass. Fakes mirror the shapes verified
against the actual SDK source (mcp_types.Tool / CallToolResult / TextContent).
"""

import pytest

from src.core.exceptions import LLMServiceError, MCPServiceError
from src.services import mcp_client as mcp_client_module
from src.services.llm import ToolUseRequest


class _FakeTool:
    def __init__(self, name: str, description: str, input_schema: dict) -> None:
        self.name = name
        self.description = description
        self.input_schema = input_schema


class _FakeListToolsResult:
    def __init__(self, tools: list[_FakeTool]) -> None:
        self.tools = tools


class _FakeTextContent:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _FakeCallToolResult:
    def __init__(self, text: str, *, is_error: bool = False) -> None:
        self.content = [_FakeTextContent(text)]
        self.is_error = is_error


class _FakeMcpClient:
    def __init__(
        self, tools: list[_FakeTool], call_results: dict[str, _FakeCallToolResult]
    ) -> None:
        self._tools = tools
        self._call_results = call_results

    async def __aenter__(self) -> "_FakeMcpClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def list_tools(self) -> _FakeListToolsResult:
        return _FakeListToolsResult(self._tools)

    async def call_tool(self, name: str, arguments: dict) -> _FakeCallToolResult:
        return self._call_results[name]


async def test_call_mcp_tools_executes_the_tools_claude_selects(monkeypatch):
    tools = [_FakeTool("calculate", "Evaluate arithmetic", {"type": "object"})]
    call_results = {"calculate": _FakeCallToolResult("42")}
    monkeypatch.setattr(
        mcp_client_module, "Client", lambda url: _FakeMcpClient(tools, call_results)
    )

    async def fake_ask_claude_for_tool_calls(*, system, user_message, tools):
        return [ToolUseRequest(id="1", name="calculate", input={"expression": "40+2"})]

    monkeypatch.setattr(
        mcp_client_module, "ask_claude_for_tool_calls", fake_ask_claude_for_tool_calls
    )

    results = await mcp_client_module.call_mcp_tools("what is 40 + 2?")

    assert len(results) == 1
    assert results[0].tool_name == "calculate"
    assert results[0].output == "42"
    assert results[0].is_error is False


async def test_call_mcp_tools_wraps_connection_failures(monkeypatch):
    def raise_connect_error(url: str):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(mcp_client_module, "Client", raise_connect_error)

    with pytest.raises(MCPServiceError):
        await mcp_client_module.call_mcp_tools("anything?")


async def test_call_mcp_tools_does_not_double_wrap_llm_errors(monkeypatch):
    tools = [_FakeTool("calculate", "Evaluate arithmetic", {"type": "object"})]
    monkeypatch.setattr(mcp_client_module, "Client", lambda url: _FakeMcpClient(tools, {}))

    async def fake_ask_claude_for_tool_calls(*, system, user_message, tools):
        raise LLMServiceError("The AI service is temporarily unavailable.")

    monkeypatch.setattr(
        mcp_client_module, "ask_claude_for_tool_calls", fake_ask_claude_for_tool_calls
    )

    with pytest.raises(LLMServiceError):
        await mcp_client_module.call_mcp_tools("anything?")
