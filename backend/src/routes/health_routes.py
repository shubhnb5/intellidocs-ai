"""Health check endpoint.

Reports whether Qdrant, the MCP server, and Redis are reachable alongside
basic app info — that's what a real readiness probe needs to do. All three
checks are cheap: get_collections() is a tiny metadata call, the MCP
server's own /health route (Phase 5) does no real work either, and PING is
what Redis exists to answer instantly.
"""

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from src.core.config import get_settings
from src.db.qdrant_client import get_qdrant_client
from src.db.redis_client import get_redis_client

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    qdrant: str
    mcp_server: str
    redis: str


@router.get(
    "/api/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Liveness/readiness check",
    description="Returns 200 with basic app info and dependency status if the API process is up.",
)
async def health_check() -> HealthResponse:
    settings = get_settings()

    try:
        get_qdrant_client().get_collections()
        qdrant_status = "ok"
    except Exception:  # any failure just means "unreachable" for this probe
        qdrant_status = "unreachable"

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{settings.mcp_server_url}/health")
        mcp_status = "ok" if response.status_code == 200 else "unreachable"
    except Exception:
        mcp_status = "unreachable"

    try:
        await get_redis_client().ping()
        redis_status = "ok"
    except Exception:
        redis_status = "unreachable"

    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.environment,
        qdrant=qdrant_status,
        mcp_server=mcp_status,
        redis=redis_status,
    )
