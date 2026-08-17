"""MCP tool: live web search.

Uses `ddgs` (a DuckDuckGo-backed metasearch library) rather than a paid
search API — zero API key, zero signup, so anyone cloning this repo can run
the full demo immediately. Trade-off worth naming out loud: it's less
reliable and lower-quality than a dedicated search API (Tavily, Serper,
Brave Search) and isn't something you'd want to depend on in production —
that's the documented upgrade path in ARCHITECTURE.md, not a gap I missed.
"""

from ddgs import DDGS
from loguru import logger
from pydantic import Field

from core.config import get_settings


def web_search(
    query: str = Field(description="What to search for, e.g. 'latest Qdrant release notes'"),
) -> list[dict[str, str]]:
    """Search the web for current information and return the top results.

    Use this when a question needs information that could not possibly be in
    the uploaded documents — current events, prices, or anything time-
    sensitive. Each result has a title, url, and short snippet.
    """
    settings = get_settings()
    try:
        results = DDGS().text(query, max_results=settings.web_search_max_results)
    except Exception as exc:
        logger.error("web_search failed for query {!r}: {}", query, exc)
        return [{"error": f"Web search failed: {exc}"}]

    return [
        {
            "title": result.get("title", ""),
            "url": result.get("href", ""),
            "snippet": result.get("body", ""),
        }
        for result in results
    ]
