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
    azure_openai_deployment: str = Field(default="gpt-4.1-mini")
    azure_openai_api_version: str = Field(default="2024-10-21")

    # MomDiary — storage (feature 009: Postgres is the single datastore).
    # The default points at a *local* Postgres so unit tests + dev shells fail
    # fast with a clear error if the developer forgot to set the URL, instead
    # of silently writing to a sqlite file on disk. Real environments (dev,
    # prod) override via env / Key Vault.
    momdiary_db_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/momdiary?ssl=disable"
    )
    # When set, test fixtures use this URL instead of `momdiary_db_url` so CI
    # and per-developer setups can isolate test data from working data.
    momdiary_test_db_url: str | None = Field(default=None)
    # SQLAlchemy async pool sizing for asyncpg. Defaults sized for Azure
    # Postgres B1ms (~50 connection cap) across 4 gunicorn workers × 2
    # instances (see specs/009-postgres-migration/research.md Decision 3).
    momdiary_db_pool_size: int = Field(default=5)
    momdiary_db_max_overflow: int = Field(default=5)
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
    # Feature 009: which SessionStore implementation to use.
    # "postgres" is the production default (multi-worker safe, survives
    # restarts). "memory" is retained for unit tests that do not need a DB.
    momdiary_session_store: Literal["memory", "postgres"] = Field(default="postgres")
    # Feature 009: cadence (seconds) at which the background TTL sweeper
    # tries to acquire the advisory lock and DELETE idle chat sessions.
    momdiary_session_sweep_interval_seconds: int = Field(default=600)

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

    # Feature 011 — Context-aware web research.
    # Hard cap on the external web-search call (FR-014). On TimeoutError
    # the runner short-circuits to outcome="research_unavailable" without
    # raising 5xx.
    momdiary_research_web_search_timeout_seconds: int = Field(default=15)
    # FR-011a: response carries between 3 and 5 trusted citations after
    # filtering; target is 4. If fewer than min remain post-filter, return
    # whatever survives down to 1; if zero, return no_sources_found.
    momdiary_research_max_sources: int = Field(default=5)
    momdiary_research_min_sources: int = Field(default=3)
    # Brave Search Web API (https://api-dashboard.search.brave.com/).
    # The research agent registers a single `brave_web_search` MAF tool
    # backed by this client; synthesis runs on the existing Azure OpenAI
    # deployment configured above. Empty `api_key` → the adapter raises
    # `ResearchUnavailableError` and the runner maps to
    # `outcome="research_unavailable"` per FR-014.
    momdiary_research_brave_api_key: str = Field(default="")
    momdiary_research_brave_endpoint: str = Field(
        default="https://api.search.brave.com/res/v1/web/search"
    )
    # Brave `safesearch` parameter — one of "off", "moderate", "strict".
    # Default "strict" because the audience is parents researching infants.
    momdiary_research_brave_safesearch: str = Field(default="strict")
    # ISO-3166 country code used to bias Brave results.
    momdiary_research_brave_country: str = Field(default="US")
    # Raw result count requested from Brave before allow/block-list filtering
    # (US4 Phase 6). Sized larger than `max_sources` so the post-filter has
    # headroom to drop low-quality results without leaving too few citations.
    momdiary_research_brave_count: int = Field(default=8)
    # Optional override path for the trusted-domain allow-list (US4).
    # Empty → use the built-in defaults shipped in `research_policy.py`.
    momdiary_research_allow_list_path: str = Field(default="")
    # Optional dedicated deployment for the scope/safety judge (US6).
    # Empty → reuse `azure_openai_deployment`.
    momdiary_research_guardrail_deployment: str = Field(default="")

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.momdiary_allowed_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
