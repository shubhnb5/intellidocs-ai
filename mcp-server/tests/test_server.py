"""Verifies the MCP wiring itself: every tool module is registered on the
server, and each one has a real description (i.e. nobody forgot a
docstring). Doesn't exercise the wire protocol -- that's the SDK's job,
already tested upstream; this just checks *our* registration code.
"""

from server import mcp


async def test_all_tools_are_registered_with_descriptions():
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}

    assert names == {"web_search", "document_metadata", "calculate"}
    for tool in tools:
        assert tool.description
