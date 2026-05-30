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

    # Intent router. When False, MAFAgentRunner bypasses the IntentRouter
    # entirely and every request runs with the full tool list. Useful for
    # A/B comparison, eval baselines, or debugging when routing is
    # suspected of being wrong.
    momdiary_intent_router_enabled: bool = Field(default=True)

    # Feature 008 — Clerk-powered caregiver authentication.
    # `clerk_secret_key`: Clerk backend secret (sk_test_... / sk_live_...).
    # `clerk_jwt_issuer`: e.g. "https://clerk.<your-app>.com" — must match `iss`.
    # `clerk_jwt_audience`: optional `aud` claim to enforce; empty disables aud check.
    # `clerk_webhook_secret`: Svix secret (whsec_...) for /v1/webhooks/clerk.
    # Settings are read from backend/.env (see backend/.env.example).
    clerk_secret_key: str = Field(default="")
    clerk_jwt_issuer: str = Field(default="")
    clerk_jwt_audience: str = Field(default="")
    clerk_webhook_secret: str = Field(default="")
    # JWKS cache TTL (seconds); force-refresh also triggered on unknown `kid`.
    clerk_jwks_cache_ttl_seconds: int = Field(default=3_600)

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.momdiary_allowed_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
