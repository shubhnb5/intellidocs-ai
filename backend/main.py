"""FastAPI application entrypoint — the composition root.

Run with: python main.py
(or: uvicorn main:app --reload)

Kept thin on purpose: this file wires together config, logging, middleware,
error handlers, and the single all_routes router. It should never need to
change when a new feature domain is added — see src/routes/all_routes.py.
"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.core.config import get_settings
from src.core.errors import (
    app_error_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from src.core.exceptions import AppError
from src.core.logging import configure_logging
from src.core.middleware import request_id_middleware
from src.db.database import init_db
from src.db.qdrant_client import ensure_collection
from src.routes.all_routes import router as all_routes

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging(debug=settings.debug)
    logger.info("starting {} in {} mode", settings.app_name, settings.environment)
    init_db()
    try:
        ensure_collection()
        logger.info("Qdrant collection '{}' ready", settings.qdrant_collection)
    except Exception as exc:
        # Don't crash the whole app if Qdrant isn't up yet — /api/health
        # reports it as unreachable, and uploads fail with a clear error
        # instead of the API never starting at all.
        logger.warning("Qdrant not reachable at startup: {}", exc)
    yield
    logger.info("shutting down {}", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description=(
        "Multi-agent document intelligence & research copilot. "
        "Upload documents, then chat with a Router Agent that decides "
        "between vector search (RAG), live tool calls (MCP), or both."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(request_id_middleware)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(all_routes)


if __name__ == "__main__":
    # Lets a beginner just run `python main.py` instead of remembering the
    # uvicorn command. --reload restarts the server on every code change,
    # same as the uvicorn CLI would.
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
