"""Centralized config for the MCP server — same pattern as the backend
(backend/src/core/config.py): every setting flows through here, documented
in .env.example, nothing reads os.environ directly elsewhere.
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

    server_name: str = Field(default="IntelliDocs Tools")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8001)
    log_level: str = Field(default="INFO")

    # The document_metadata tool calls back into the main backend's REST API
    # rather than sharing its database — this server stays a standalone
    # process reachable over the network, same as any other MCP server would
    # be from the agent's point of view.
    backend_api_url: str = Field(default="http://localhost:8000")
    backend_api_timeout_seconds: float = Field(default=10.0)
    # Sent as X-Internal-Api-Key on that call — must match the backend's own
    # INTERNAL_API_KEY. See backend/src/core/auth_dependency.py.
    internal_api_key: str = Field(default="")

    web_search_max_results: int = Field(default=5)


@lru_cache
def get_settings() -> Settings:
    return Settings()
