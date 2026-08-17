from src.services import tool_agent as tool_agent_module
from src.services.mcp_client import ToolCallResult


async def test_tool_node_returns_results_and_event(monkeypatch):
    results = [
        ToolCallResult(
            tool_name="calculate", tool_input={"expression": "2+2"}, output="4", is_error=False
        )
    ]

    async def fake_call_mcp_tools(question: str):
        return results

    monkeypatch.setattr(tool_agent_module, "call_mcp_tools", fake_call_mcp_tools)

    result = await tool_agent_module.tool_node({"question": "what is 2+2?"})

    assert result["tool_results"] == results
    assert "calculate" in result["events"][0].message


async def test_tool_node_handles_no_tools_called(monkeypatch):
    async def fake_call_mcp_tools(question: str):
        return []

    monkeypatch.setattr(tool_agent_module, "call_mcp_tools", fake_call_mcp_tools)

    result = await tool_agent_module.tool_node({"question": "anything?"})

    assert result["tool_results"] == []
    assert "none" in result["events"][0].message
