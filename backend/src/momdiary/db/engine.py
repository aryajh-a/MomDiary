"""Async SQLAlchemy engine + session factory."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import event
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


def _install_sqlite_pragmas(engine: AsyncEngine) -> None:
    """WAL + busy_timeout + FK enforcement on every aiosqlite connection.

    Without these, a single concurrent writer (e.g. the per-request
    `user_sessions` slide) raises `database is locked` immediately because
    SQLite's default `journal_mode=DELETE` serialises everything and the
    default `busy_timeout` is 0.
    """
    if not engine.url.drivername.startswith("sqlite"):
        return

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        try:
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA busy_timeout=10000")  # 10s
            cur.execute("PRAGMA foreign_keys=ON")
        finally:
            cur.close()


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        logger.info("db.engine.creating", url=settings.momdiary_db_url)
        _engine = create_async_engine(
            settings.momdiary_db_url,
            future=True,
            echo=False,
            connect_args={"timeout": 30},  # sqlite3.connect busy timeout (s)
        )
        _install_sqlite_pragmas(_engine)
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
