"""Tool Agent: calls the MCP server's tools when the Router says the
question needs live or computed information. Deciding *which* tool(s) to
call is delegated to Claude (see services/llm.ask_claude_for_tool_calls);
executing them against the real MCP server is this agent's own job (see
services/mcp_client.py).
"""

from src.services.agent_state import AgentEvent, AgentState
from src.services.mcp_client import call_mcp_tools


async def tool_node(state: AgentState) -> dict:
    results = await call_mcp_tools(state["question"])
    tool_names = ", ".join(result.tool_name for result in results) or "none"
    return {
        "tool_results": results,
        "events": [
            AgentEvent(agent="tool", message=f"Called MCP tool(s): {tool_names}."),
        ],
    }
