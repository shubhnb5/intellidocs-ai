"""Single aggregation point for every route domain.

main.py only ever imports this one router — it never has to change as new
domains are added. Adding a new feature domain means: add its file under
src/routes/, import its router here, and include it below. main.py stays
untouched.
"""

from fastapi import APIRouter

from src.routes.auth_routes import router as auth_router
from src.routes.chat_routes import router as chat_router
from src.routes.chat_websocket import router as chat_websocket_router
from src.routes.document_routes import router as documents_router
from src.routes.health_routes import router as health_router

router = APIRouter()

# Health
router.include_router(health_router)

# Auth — register/login/refresh/logout/me (Phase 8)
router.include_router(auth_router)

# Documents — upload, chunking, embeddings (Phase 2)
router.include_router(documents_router)

# Chat — Router/Retrieval/Tool/Summarizer multi-agent pipeline (Phase 6),
# same URL as Phase 3's original plain-RAG endpoint.
router.include_router(chat_router)

# Chat, streaming — same pipeline over a WebSocket (Phase 7): live agent
# activity + token-by-token answer instead of one blocking response.
router.include_router(chat_websocket_router)
