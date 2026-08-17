"""Centralized app configuration.

All configuration flows through here — nothing reads os.environ directly
elsewhere in the codebase. That's what lets us document every setting in one
place (see .env.example) and validate it at startup instead of failing deep
inside a request handler.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_name: str = "IntelliDocs AI"
    environment: str = Field(default="development")  # development | staging | production
    debug: bool = Field(default=True)

    # --- CORS ---
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # --- LLM (Anthropic Claude) ---
    anthropic_api_key: str = Field(default="")
    anthropic_model: str = Field(default="claude-sonnet-5")
    # low/medium/high/xhigh/max — how hard the model thinks per request.
    # "medium" is a deliberate cost/quality choice for a Q&A endpoint, not the
    # API default ("high") — see services/llm.py.
    claude_effort: str = Field(default="medium")
    claude_timeout_seconds: float = Field(default=30.0)
    claude_max_retries: int = Field(default=2)

    # --- Vector DB (Qdrant) ---
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_collection: str = Field(default="intellidocs_chunks")

    # --- Document ingestion (Phase 2) ---
    max_upload_size_mb: int = Field(default=20)
    # Recursive splitter target size/overlap, in characters (not tokens — see
    # services/chunking.py for why that trade-off is fine here).
    chunk_size: int = Field(default=1000)
    chunk_overlap: int = Field(default=150)

    # --- Embeddings ---
    # Local ONNX model via fastembed — no external API call per chunk during
    # ingestion. embedding_dim MUST match this model's output size; it's used
    # to create the Qdrant collection, so changing the model requires
    # recreating the collection too.
    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5")
    embedding_dim: int = Field(default=384)

    # --- Relational DB (document metadata + computed NLP fields) ---
    # SQLite for local dev/demo — zero setup, just a file. Swapping to
    # Postgres in production is a DATABASE_URL change (plus adding a
    # psycopg2 dependency); SQLAlchemy abstracts the rest.
    database_url: str = Field(default="sqlite:///./intellidocs.db")

    # --- NLP pipeline (Phase 4) ---
    # Cap on how much of a document's text spaCy/summarization processes.
    # Keeps upload latency bounded for very large documents; entities/topics/
    # summary end up based on the first N chars rather than the whole thing.
    nlp_max_chars: int = Field(default=50_000)

    # --- MCP server (Phase 5) ---
    # The Tool Agent connects here as an MCP client; see services/mcp_client.py.
    mcp_server_url: str = Field(default="http://localhost:8001")

    # --- Redis (cache + rate limiting) (Phase 8) ---
    redis_url: str = Field(default="redis://localhost:6379/0")
    # How long a GET /api/documents response is cached per-user before a
    # fresh DB read. Invalidated immediately on upload, so this is purely a
    # bound on staleness for concurrent readers, not the only invalidation path.
    document_cache_ttl_seconds: int = Field(default=30)
    # Fixed-window limit shared by the expensive/abuseable endpoints (login,
    # register, chat ask, document upload) — see core/rate_limit.py.
    rate_limit_requests: int = Field(default=20)
    rate_limit_window_seconds: int = Field(default=60)

    # --- Auth (Phase 8) ---
    jwt_secret_key: str = Field(default="")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=30)
    jwt_refresh_token_expire_days: int = Field(default=7)
    # Shared secret the MCP server presents (via the X-Internal-Api-Key
    # header) to call GET /api/documents/{id} as a trusted service rather
    # than a logged-in user — see routes/document_routes.py. Must match
    # the mcp-server process's own INTERNAL_API_KEY. Left blank disables the
    # bypass entirely (the document_metadata tool will 401 until it's set).
    internal_api_key: str = Field(default="")


@lru_cache
def get_settings() -> Settings:
    """Cached so Settings() — which reads the environment and .env file —
    only runs once per process instead of on every request."""
    return Settings()
