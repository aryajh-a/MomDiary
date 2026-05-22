"""Application settings loaded from environment variables (FR-012, Principle IV)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Azure AI Foundry / Azure OpenAI (auth via DefaultAzureCredential — Principle IV)
    azure_openai_endpoint: str = Field(default="")
    azure_openai_deployment: str = Field(default="gpt-4.1")
    azure_openai_api_version: str = Field(default="2024-10-21")

    # MomDiary
    momdiary_db_url: str = Field(default="sqlite+aiosqlite:///./momdiary.db")
    momdiary_default_timezone: str = Field(default="America/Los_Angeles")
    momdiary_app_env: Literal["dev", "test", "prod"] = Field(default="dev")
    momdiary_allowed_origins: str = Field(default="http://localhost:5173")

    # Chat session store (feature 003-chat-session-store).
    # Per-session idle TTL in seconds (FR-010). Default: 24h.
    momdiary_session_ttl_seconds: int = Field(default=86_400)
    # Per-session FIFO turn-pair cap (FR-009). One pair == caregiver + assistant.
    momdiary_session_max_turns: int = Field(default=50)
    # Global LRU cap on resident sessions (FR-011).
    momdiary_session_max_sessions: int = Field(default=100)
    # Max bytes per caregiver message stored in session history (FR-012).
    momdiary_session_message_max_bytes: int = Field(default=4_096)
    # Token-aware trim budget when constructing the agent prompt (FR-013).
    # Conservative under the gpt-4.1 16K context window.
    momdiary_session_prompt_token_budget: int = Field(default=12_000)

    # Auth / cookie settings (feature 006).
    momdiary_session_cookie_name: str = Field(default="momdiary_session")
    momdiary_session_cookie_ttl_days: int = Field(default=30)
    # Set False in dev when serving over plain http.
    momdiary_session_cookie_secure: bool = Field(default=False)
    momdiary_session_cookie_samesite: Literal["lax", "strict", "none"] = Field(
        default="lax"
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.momdiary_allowed_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
