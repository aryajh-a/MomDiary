"""Background TTL sweeper for `chat_sessions` (feature 009, US2).

Runs as a long-lived asyncio task in the FastAPI lifespan. Every
`momdiary_session_sweep_interval_seconds` it tries to acquire a Postgres
advisory lock — only the worker that wins the lock issues the DELETE, so N
workers sweeping concurrently still produce 1 DB roundtrip per cycle
(Decision 7 in research.md).

The lock id is an arbitrary but stable bigint (`0x4D4D44545452`, "MMDTTR"
in ASCII) so multiple deployments of the same app target the same lock.

Cancellation: the task is cancelled in lifespan teardown; the inner sleep
catches `asyncio.CancelledError` and exits cleanly.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from momdiary.observability.logging import get_logger

logger = get_logger(__name__)

# Stable bigint key for pg_try_advisory_lock. ASCII 'MMDTTR' interpreted as
# hex bytes 4D 4D 44 54 54 52.
_SWEEPER_LOCK_KEY = 0x4D4D44545452


async def _try_sweep_once(
    session_factory: async_sessionmaker[AsyncSession],
    ttl_seconds: int,
) -> int:
    """One sweep cycle. Returns rows deleted, or -1 if lock not acquired."""
    async with session_factory() as s:
        got_lock_row = (
            await s.execute(
                text("SELECT pg_try_advisory_lock(:k)"),
                {"k": _SWEEPER_LOCK_KEY},
            )
        ).scalar_one()
        if not got_lock_row:
            return -1
        try:
            result = await s.execute(
                text(
                    "DELETE FROM chat_sessions "
                    "WHERE updated_at < NOW() - make_interval(secs => :ttl)"
                ),
                {"ttl": ttl_seconds},
            )
            await s.commit()
            deleted = result.rowcount or 0
        finally:
            await s.execute(
                text("SELECT pg_advisory_unlock(:k)"),
                {"k": _SWEEPER_LOCK_KEY},
            )
            await s.commit()
        return deleted


async def run_session_ttl_sweeper(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    ttl_seconds: int,
    interval_seconds: int,
    sweep_fn: Callable[..., Awaitable[int]] = _try_sweep_once,
) -> None:
    """Long-running task: sleep `interval_seconds`, try-lock, DELETE expired.

    Survives single-cycle failures (logs and continues). Exits cleanly on
    asyncio.CancelledError so the FastAPI lifespan can join it on shutdown.
    """
    logger.info(
        "session.sweeper.starting",
        ttl_seconds=ttl_seconds,
        interval_seconds=interval_seconds,
    )
    try:
        while True:
            try:
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                logger.info("session.sweeper.cancelled")
                raise
            try:
                deleted = await sweep_fn(session_factory, ttl_seconds)
            except Exception as exc:  # noqa: BLE001 — log and continue
                logger.warning(
                    "session.sweeper.cycle_failed", error=str(exc)
                )
                continue
            if deleted < 0:
                logger.debug("session.sweeper.lock_held_elsewhere")
            elif deleted > 0:
                logger.info("session.sweeper.swept", deleted=deleted)
    finally:
        logger.info("session.sweeper.stopped")
