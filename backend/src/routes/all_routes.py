"""Single aggregation point for every route domain.

main.py only ever imports this one router — it never has to change as new
domains are added. Adding a new feature domain (Documents, Chat, Auth, ...)
means: add its folder under src/routes/, import its router here, and
include it below. main.py stays untouched.
"""

from fastapi import APIRouter

from src.routes.Health.health import router as health_router

router = APIRouter()

# Health
router.include_router(health_router)

# Documents — lands in Phase 2 (upload, chunking, embeddings)
# Chat — lands in Phase 3 (RAG Q&A) and Phase 6 (multi-agent orchestration)
# Auth — lands in Phase 8 (JWT login/refresh)
