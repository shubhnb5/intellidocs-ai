"""MCP tool: look up a previously uploaded document's metadata by calling
back into the main backend's REST API (GET /api/documents/{id} from Phase 4).

This is the MCP server acting as a bridge between an agent and our own
system — the same pattern it would use to reach any other internal or
third-party service. It's a separate network call, not a shared database or
a direct import of backend code, so this server stays genuinely standalone.

Errors are returned as a plain {"error": "..."} dict rather than raised,
where there's a clearer message to give than the raw exception (a connection
failure, a 404). Anything else is left to propagate — the MCP SDK's own
dispatcher already catches tool exceptions and reports them to the calling
agent as a tool error, so this doesn't need to defensively catch everything.
"""

import httpx
from loguru import logger
from pydantic import Field

from core.config import get_settings


async def document_metadata(
    document_id: str = Field(description="The document's ID, returned when it was uploaded"),
) -> dict:
    """Look up a previously uploaded document's filename, chunk count,
    extracted entities, topics, and auto-summary.

    Use this when a question refers to a specific document by ID rather than
    asking about its content — e.g. "when was this uploaded" or "what is
    this document about" without needing full-text retrieval.
    """
    settings = get_settings()
    url = f"{settings.backend_api_url}/api/documents/{document_id}"
    headers = {"X-Internal-Api-Key": settings.internal_api_key}

    try:
        async with httpx.AsyncClient(timeout=settings.backend_api_timeout_seconds) as client:
            response = await client.get(url, headers=headers)
    except httpx.RequestError as exc:
        logger.error("document_metadata: backend unreachable: {}", exc)
        return {"error": f"Could not reach the document service: {exc}"}

    if response.status_code == 404:
        return {"error": f"No document with id '{document_id}'."}

    response.raise_for_status()
    return response.json()
