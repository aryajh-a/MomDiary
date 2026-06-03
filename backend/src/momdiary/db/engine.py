"""Async SQLAlchemy engine + session factory.

Feature 009 — Postgres is the single supported runtime backend. The engine
asserts the configured URL is `postgresql+asyncpg://...` and carries an
explicit `ssl=...` parameter, so a misconfigured deployment fails fast at
startup rather than silently falling back to SQLite.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from momdiary.config import get_settings
from momdiary.observability.logging import get_logger

logger = get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _validate_postgres_url(url: str) -> None:
    """Hard-fail if the runtime URL is not asyncpg-over-TLS-aware (FR-002)."""
    if not url.startswith("postgresql+asyncpg://"):
        raise RuntimeError(
            "MOMDIARY_DB_URL must use the postgresql+asyncpg driver "
            f"(got: {url.split('://', 1)[0]}://...). SQLite is no longer a "
            "supported runtime backend (feature 009)."
        )
    if "ssl=" not in url:
        raise RuntimeError(
            "MOMDIARY_DB_URL must include an explicit `ssl=` query param "
            "(use `ssl=require` for Azure Postgres Flex, `ssl=disable` for "
            "a local dev container)."
        )


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _validate_postgres_url(settings.momdiary_db_url)
        logger.info(
            "db.engine.creating",
            url_scheme=settings.momdiary_db_url.split("://", 1)[0],
            pool_size=settings.momdiary_db_pool_size,
            max_overflow=settings.momdiary_db_max_overflow,
        )
        _engine = create_async_engine(
            settings.momdiary_db_url,
            future=True,
            echo=False,
            pool_size=settings.momdiary_db_pool_size,
            max_overflow=settings.momdiary_db_max_overflow,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        logger.info("db.engine.disposing")
        await _engine.dispose()
    _engine = None
    _session_factory = None


def reset_engine_for_tests() -> None:
    """Test-only helper; do not call from production code."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None
