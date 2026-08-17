"""IntelliDocs MCP server — exposes tools an agent can call over the Model
Context Protocol: web search, document metadata lookup, and a calculator.
The Router/Tool agents built in Phase 6 connect to this as an ordinary MCP
client; nothing about it is IntelliDocs-specific beyond the tools themselves.

Run standalone (stdio, for local tools like the MCP Inspector):
    uv run mcp dev server.py

Run over HTTP (what the agent actually connects to):
    python server.py
    # or, equivalently, with more control over workers/reload:
    uvicorn server:app --host 0.0.0.0 --port 8001
"""

import sys

from loguru import logger
from mcp.server import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse

from core.config import get_settings
from tools.calculator import calculate
from tools.document_metadata import document_metadata
from tools.web_search import web_search

settings = get_settings()

logger.remove()
logger.add(sys.stdout, serialize=True, level=settings.log_level)

mcp = MCPServer(settings.server_name, log_level=settings.log_level)

# Registering plain functions here (rather than decorating them in-place in
# tools/*.py) keeps each tool module free of any dependency on the server
# object, so they stay independently importable and testable.
mcp.tool()(web_search)
mcp.tool()(document_metadata)
mcp.tool()(calculate)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "server": settings.server_name})


# ASGI app — what `uvicorn server:app` and (eventually) Docker run.
app = mcp.streamable_http_app()


if __name__ == "__main__":
    logger.info("starting {} on {}:{}", settings.server_name, settings.host, settings.port)
    mcp.run(transport="streamable-http", host=settings.host, port=settings.port)
