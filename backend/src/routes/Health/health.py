"""Health check endpoint.

Deliberately dependency-free right now (Phase 1: no vector store/cache exist
yet). From Phase 8 onward this also reports Qdrant/Redis reachability, which
is what a real readiness probe needs to do.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from src.core.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str


@router.get(
    "/api/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Liveness/readiness check",
    description="Returns 200 with basic app info if the API process is up.",
)
async def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.environment,
    )
