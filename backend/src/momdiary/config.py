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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
