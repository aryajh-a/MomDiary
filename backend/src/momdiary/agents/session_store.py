"""In-memory chat session store (feature 003).

The store is a process-lifetime singleton owned by the FastAPI app. It maps
opaque, server-issued UUID-v4 session ids to bounded conversation history.
See `specs/003-chat-session-store/data-model.md` for the invariants and
`plan.md#agent-invocation-flow-history-inclusion--fr-004` for the call
sequence the dispatcher uses.

Bounded resources (all configurable via `momdiary.config.Settings`):

* per-session FIFO turn cap (FR-009)
* per-session idle TTL (FR-010)
* global LRU session cap (FR-011)
* per-message byte cap (FR-012)
* token-aware trim on read (FR-013)

Concurrency: append / recent_view do not await anything between read and
mutation; `deque.append` is atomic on the asyncio single-threaded loop. The
public `ChatSession.lock` is provided so callers (the dispatcher) can
serialize the multi-step ``recent_view -> agent.run -> append`` transaction
end-to-end (FR-014).
"""

from __future__ import annotations

import asyncio
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol

from momdiary.observability.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Entities (data-model.md §1, §2)
# ---------------------------------------------------------------------------


TurnRole = Literal["caregiver", "assistant"]
TurnOutcome = Literal[
    "created", "updated", "deleted", "clarification_requested", "rejected"
]


@dataclass(slots=True)
class ChatTurn:
    """A single caregiver or assistant turn within a session."""

    role: TurnRole
    text: str
    correlation_id: str
    created_at: datetime
    outcome: TurnOutcome | None = None
    entry_type: str | None = None
    entry_id: int | None = None


@dataclass
class ChatSession:
    """An identified, bounded sequence of turns."""

    id: str
    created_at: datetime
    last_activity_at: datetime
    turns: deque[ChatTurn]
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SessionMessageTooLargeError(ValueError):
    """Raised when an appended ChatTurn exceeds the configured byte cap."""


# ---------------------------------------------------------------------------
# Token estimator (research.md §4)
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    """Cheap heuristic: ~4 chars per token + a small per-message overhead."""
    return (len(text) // 4) + 4


def _estimate_turn_tokens(turn: ChatTurn) -> int:
    return _estimate_tokens(turn.text)


# ---------------------------------------------------------------------------
# Protocol + in-memory backend
# ---------------------------------------------------------------------------


class SessionStore(Protocol):
    async def get_or_create(
        self, session_id: str | None, *, correlation_id: str | None = None
    ) -> ChatSession: ...

    async def append(self, session: ChatSession, turn: ChatTurn) -> None: ...

    async def recent_view(
        self, session: ChatSession, token_budget: int
    ) -> list[ChatTurn]: ...

    async def evict_expired(self, now: datetime | None = None) -> int: ...


def _utc_now() -> datetime:
    return datetime.now(UTC)


class InMemorySessionStore:
    """Process-local in-memory `SessionStore` implementation."""

    def __init__(
        self,
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
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_turns = max_turns
        self._max_sessions = max_sessions
        self._message_max_bytes = message_max_bytes
        self._now_fn = now_fn
        self._sessions: dict[str, ChatSession] = {}
        self._store_lock = asyncio.Lock()

    # -- public API -----------------------------------------------------

    async def get_or_create(
        self, session_id: str | None, *, correlation_id: str | None = None
    ) -> ChatSession:
        async with self._store_lock:
            now = self._now_fn()
            # Lazy TTL eviction sweep before any lookup.
            self._sweep_expired_locked(now, correlation_id=correlation_id)

            if session_id and session_id in self._sessions:
                s = self._sessions[session_id]
                s.last_activity_at = now
                return s

            # Either no id provided, or unknown / already-swept-expired id.
            new_id = str(uuid.uuid4())
            # Enforce global LRU cap before insertion.
            while len(self._sessions) >= self._max_sessions:
                victim_id = min(
                    self._sessions, key=lambda k: self._sessions[k].last_activity_at
                )
                del self._sessions[victim_id]
                logger.info(
                    "session.evicted",
                    reason="lru",
                    evicted_session_id=victim_id[:8],
                    correlation_id=correlation_id,
                )

            s = ChatSession(
                id=new_id,
                created_at=now,
                last_activity_at=now,
                turns=deque(maxlen=self._max_turns * 2),
            )
            self._sessions[new_id] = s
            logger.info(
                "session.created",
                session_id=new_id[:8],
                correlation_id=correlation_id,
            )
            return s

    async def append(self, session: ChatSession, turn: ChatTurn) -> None:
        text_bytes = len(turn.text.encode("utf-8"))
        if text_bytes > self._message_max_bytes:
            raise SessionMessageTooLargeError(
                f"caregiver message of {text_bytes} bytes exceeds the "
                f"configured cap of {self._message_max_bytes} bytes"
            )
        session.turns.append(turn)
        session.last_activity_at = self._now_fn()
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
        session.last_activity_at = self._now_fn()
        if not session.turns:
            return []
        # Walk newest -> oldest, accumulate token estimate; cut once over budget.
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
        async with self._store_lock:
            now = now if now is not None else self._now_fn()
            return self._sweep_expired_locked(now, correlation_id=None)

    # -- internals ------------------------------------------------------

    def _sweep_expired_locked(
        self, now: datetime, *, correlation_id: str | None
    ) -> int:
        cutoff = now - self._ttl
        expired = [
            sid
            for sid, s in self._sessions.items()
            if s.last_activity_at < cutoff
        ]
        for sid in expired:
            del self._sessions[sid]
            logger.info(
                "session.expired",
                session_id=sid[:8],
                correlation_id=correlation_id,
            )
        return len(expired)

    # -- introspection (test-only) --------------------------------------

    def _resident_count(self) -> int:
        return len(self._sessions)

    def _peek(self, session_id: str) -> ChatSession | None:
        return self._sessions.get(session_id)
