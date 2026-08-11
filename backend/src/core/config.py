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

    # --- Vector DB (Qdrant) --- wired up in Phase 2
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_collection: str = Field(default="intellidocs_chunks")

    # --- Redis (cache + rate limiting) --- wired up in Phase 8
    redis_url: str = Field(default="redis://localhost:6379/0")

    # --- Auth --- wired up in Phase 8
    jwt_secret_key: str = Field(default="")
    jwt_access_token_expire_minutes: int = Field(default=30)
    jwt_refresh_token_expire_days: int = Field(default=7)


@lru_cache
def get_settings() -> Settings:
    """Cached so Settings() — which reads the environment and .env file —
    only runs once per process instead of on every request."""
    return Settings()
