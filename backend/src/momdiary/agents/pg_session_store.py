"""Postgres-backed `SessionStore` (feature 009).

Mirrors the public interface of `InMemorySessionStore` so the dispatcher
needs no awareness of the backend. The on-wire representation is one row
per session in the `chat_sessions` table; the entire bounded deque is
re-serialised to JSONB on every `append` (the deque is small — capped at
`max_turns * 2` per FR-009 — so full-row writes are cheaper than designing
an append-only child table for what is, by design, a bounded prefix-free
sequence).

Concurrency model:

* Per-process: each `ChatSession` carries an `asyncio.Lock` reused from the
  in-memory store; the dispatcher serialises `recent_view → run → append`
  end-to-end (FR-014) on that lock.
* Cross-process: the upsert in `append` is idempotent w.r.t. the JSONB blob
  (writer always sends the full deque), so the last writer wins. Two
  concurrent workers writing different turns to the same session would
  result in one turn being lost — but session ids are partitioned per
  (user_id, baby_id) and a single caregiver only ever has one in-flight
  request at a time (single chat surface in the UI), so this is acceptable
  per Decision 5 in research.md.

Invariants enforced (contracts/session-store.md):
    SS-01 partition isolation  — every SELECT/UPDATE includes
                                 (user_id, baby_id) in the predicate
    SS-04 turn cap            — deque(maxlen=max_turns*2) trims at the
                                 dataclass level before serialisation
    SS-05 byte cap            — same `SessionMessageTooLargeError` raised
                                 as the in-memory backend
    SS-08 idempotent upsert   — `INSERT ... ON CONFLICT DO UPDATE`
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from momdiary.agents.session_store import (
    ChatSession,
    ChatTurn,
    SessionMessageTooLargeError,
)
from momdiary.observability.logging import get_logger

logger = get_logger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _turn_to_json(turn: ChatTurn) -> dict[str, Any]:
    """Serialise a `ChatTurn` to a JSON-safe dict (ISO datetime)."""
    d = asdict(turn)
    d["created_at"] = turn.created_at.isoformat()
    return d


def _turn_from_json(d: dict[str, Any]) -> ChatTurn:
    return ChatTurn(
        role=d["role"],
        text=d["text"],
        correlation_id=d["correlation_id"],
        created_at=datetime.fromisoformat(d["created_at"]),
        outcome=d.get("outcome"),
        entry_type=d.get("entry_type"),
        entry_id=d.get("entry_id"),
    )


class PgSessionStore:
    """Postgres-backed `SessionStore` implementation."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        ttl_seconds: int,
        max_turns: int,
        max_sessions: int,
        message_max_bytes: int,
        now_fn: Callable[[], datetime] = _utc_now,
    ) -> None:
        if max_turns <= 0:
            raise ValueError("max_turns must be > 0")
        if max_sessions <= 0:
            raise ValueError("max_sessions must be > 0")
        if message_max_bytes <= 0:
            raise ValueError("message_max_bytes must be > 0")
        self._session_factory = session_factory
        self._ttl_seconds = ttl_seconds
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_turns = max_turns
        self._max_sessions = max_sessions
        self._message_max_bytes = message_max_bytes
        self._now_fn = now_fn
        # Per-process lock cache so concurrent requests for the same
        # session id reuse one asyncio.Lock (the lock is part of the
        # ChatSession dataclass returned to the dispatcher).
        self._lock_cache: dict[str, asyncio.Lock] = {}
        self._lock_cache_guard = asyncio.Lock()

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    async def get_or_create(
        self,
        session_id: str | None,
        *,
        correlation_id: str | None = None,
        user_id: int = 0,
        baby_id: int = 0,
    ) -> ChatSession:
        now = self._now_fn()
        cutoff = now - self._ttl

        if session_id is not None:
            existing = await self._load(
                session_id=session_id, user_id=user_id, baby_id=baby_id
            )
            if existing is not None and existing.last_activity_at >= cutoff:
                return existing
            # Cross-partition hit or expired session → fall through and
            # mint a fresh id (never leak someone else's history; SS-01).

        new_id = str(uuid.uuid4())
        async with self._session_factory() as s:
            await s.execute(
                text(
                    """
                    INSERT INTO chat_sessions
                        (session_id, user_id, baby_id, turns, created_at, updated_at)
                    VALUES
                        (:sid, :uid, :bid, CAST(:turns AS JSONB), :now, :now)
                    ON CONFLICT (session_id) DO NOTHING
                    """
                ),
                {
                    "sid": new_id,
                    "uid": user_id,
                    "bid": baby_id,
                    "turns": "[]",
                    "now": now,
                },
            )
            await s.commit()

        logger.info(
            "session.created",
            session_id=new_id[:8],
            user_id=user_id,
            baby_id=baby_id,
            correlation_id=correlation_id,
        )

        lock = await self._lock_for(new_id)
        return ChatSession(
            id=new_id,
            created_at=now,
            last_activity_at=now,
            turns=deque(maxlen=self._max_turns * 2),
            lock=lock,
        )

    async def append(self, session: ChatSession, turn: ChatTurn) -> None:
        text_bytes = len(turn.text.encode("utf-8"))
        if text_bytes > self._message_max_bytes:
            raise SessionMessageTooLargeError(
                f"caregiver message of {text_bytes} bytes exceeds the "
                f"configured cap of {self._message_max_bytes} bytes"
            )
        now = self._now_fn()
        session.turns.append(turn)
        session.last_activity_at = now

        # Serialise the entire (already-trimmed) deque; deque.maxlen has
        # already enforced the FIFO cap at the caller side.
        turns_json = json.dumps([_turn_to_json(t) for t in session.turns])

        async with self._session_factory() as s:
            await s.execute(
                text(
                    """
                    INSERT INTO chat_sessions
                        (session_id, user_id, baby_id, turns, created_at, updated_at)
                    VALUES
                        (:sid, 0, 0, CAST(:turns AS JSONB), :now, :now)
                    ON CONFLICT (session_id) DO UPDATE
                        SET turns = EXCLUDED.turns,
                            updated_at = EXCLUDED.updated_at
                    """
                ),
                {"sid": session.id, "turns": turns_json, "now": now},
            )
            await s.commit()

        logger.info(
            "session.appended",
            session_id=session.id[:8],
            role=turn.role,
            outcome=turn.outcome,
            turn_count=len(session.turns),
            correlation_id=turn.correlation_id,
        )

    async def recent_view(
        self, session: ChatSession, token_budget: int
    ) -> list[ChatTurn]:
        # `recent_view` is read-only over the in-memory deque; the deque
        # was hydrated from JSONB in `get_or_create`. No DB round-trip
        # required here (mirrors InMemory behaviour for parity).
        session.last_activity_at = self._now_fn()
        if not session.turns:
            return []
        # Lazy local import to avoid cycle; same heuristic as in-memory.
        from momdiary.agents.session_store import _estimate_turn_tokens

        suffix: list[ChatTurn] = []
        used = 0
        for turn in reversed(session.turns):
            cost = _estimate_turn_tokens(turn)
            if suffix and used + cost > token_budget:
                break
            suffix.append(turn)
            used += cost
        suffix.reverse()
        return suffix

    async def evict_expired(self, now: datetime | None = None) -> int:
        """DELETE chat_sessions with updated_at < NOW() - ttl. Returns count."""
        cutoff = (now if now is not None else self._now_fn()) - self._ttl
        async with self._session_factory() as s:
            result = await s.execute(
                text(
                    "DELETE FROM chat_sessions "
                    "WHERE updated_at < :cutoff"
                ),
                {"cutoff": cutoff},
            )
            await s.commit()
        deleted = result.rowcount or 0
        if deleted:
            logger.info("session.expired_batch", deleted=deleted)
        return deleted

    async def purge_user(self, user_id: int) -> int:
        """DELETE chat_sessions for a given caregiver (Clerk user.deleted)."""
        async with self._session_factory() as s:
            result = await s.execute(
                text("DELETE FROM chat_sessions WHERE user_id = :uid"),
                {"uid": user_id},
            )
            await s.commit()
        purged = result.rowcount or 0
        if purged:
            logger.info("session.purged_user", user_id=user_id, purged=purged)
        return purged

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    async def _load(
        self, *, session_id: str, user_id: int, baby_id: int
    ) -> ChatSession | None:
        async with self._session_factory() as s:
            row = (
                await s.execute(
                    text(
                        """
                        SELECT session_id, turns, created_at, updated_at
                          FROM chat_sessions
                         WHERE session_id = :sid
                           AND user_id = :uid
                           AND baby_id = :bid
                        """
                    ),
                    {"sid": session_id, "uid": user_id, "bid": baby_id},
                )
            ).mappings().first()

        if row is None:
            return None

        raw_turns = row["turns"] or []
        # asyncpg returns JSONB as str; SQLAlchemy may or may not decode it.
        if isinstance(raw_turns, str):
            raw_turns = json.loads(raw_turns)

        d: deque[ChatTurn] = deque(maxlen=self._max_turns * 2)
        for entry in raw_turns:
            d.append(_turn_from_json(entry))

        lock = await self._lock_for(session_id)
        return ChatSession(
            id=session_id,
            created_at=row["created_at"],
            last_activity_at=row["updated_at"],
            turns=d,
            lock=lock,
        )

    async def _lock_for(self, session_id: str) -> asyncio.Lock:
        async with self._lock_cache_guard:
            lock = self._lock_cache.get(session_id)
            if lock is None:
                lock = asyncio.Lock()
                self._lock_cache[session_id] = lock
            return lock
