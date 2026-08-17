"""SQL engine + session factory for document metadata and computed NLP
fields (see sql_models.py). Separate from qdrant_client.py on purpose —
Qdrant is a vector index, this is the relational store, and they're wired up
independently so either can change without touching the other.
"""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import get_settings
from src.db.sql_models import Base


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    # SQLite's default driver forbids using a connection from a different
    # thread than created it; FastAPI's threadpool means that thread varies
    # per request, so this flag is required for SQLite specifically.
    connect_args = (
        {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    )
    return create_engine(settings.database_url, connect_args=connect_args)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def init_db() -> None:
    """Create tables if they don't exist yet. Called once at startup (see
    main.py's lifespan). SQLite needs no migration tool at this project's
    size; Postgres in production would use Alembic instead of create_all."""
    Base.metadata.create_all(bind=get_engine())


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency — one session per request, always closed after."""
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()
