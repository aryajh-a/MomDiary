"""Phase 2 unit tests for `InMemorySessionStore` (feature 003)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from momdiary.agents.session_store import (
    ChatTurn,
    InMemorySessionStore,
    SessionMessageTooLargeError,
    _estimate_turn_tokens,
)


def _make_store(
    *,
    ttl_seconds: int = 3600,
    max_turns: int = 5,
    max_sessions: int = 3,
    message_max_bytes: int = 1024,
    now_value: datetime | None = None,
) -> tuple[InMemorySessionStore, list[datetime]]:
    """Build a store with an injectable `now`. Returns (store, now_holder)."""
    now_holder = [now_value or datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc)]

    def now_fn() -> datetime:
        return now_holder[0]

    store = InMemorySessionStore(
        ttl_seconds=ttl_seconds,
        max_turns=max_turns,
        max_sessions=max_sessions,
        message_max_bytes=message_max_bytes,
        now_fn=now_fn,
    )
    return store, now_holder


def _caregiver_turn(text: str = "hi", cid: str = "c1") -> ChatTurn:
    return ChatTurn(
        role="caregiver",
        text=text,
        correlation_id=cid,
        created_at=datetime(2026, 5, 18, tzinfo=timezone.utc),
    )


# T004 -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_or_create_none_issues_fresh_uuid() -> None:
    store, _ = _make_store()
    s1 = await store.get_or_create(None)
    s2 = await store.get_or_create(None)
    assert s1.id != s2.id
    # UUID v4 length
    assert len(s1.id) == 36 and s1.id.count("-") == 4


@pytest.mark.asyncio
async def test_get_or_create_known_id_returns_same_session() -> None:
    store, _ = _make_store()
    s1 = await store.get_or_create(None)
    s2 = await store.get_or_create(s1.id)
    assert s2 is s1


@pytest.mark.asyncio
async def test_get_or_create_unknown_id_issues_fresh() -> None:
    store, _ = _make_store()
    s = await store.get_or_create("not-a-real-id")
    assert s.id != "not-a-real-id"


# T005 -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_fifo_cap_holds_at_max_turns_times_two() -> None:
    max_turns = 4
    store, _ = _make_store(max_turns=max_turns)
    session = await store.get_or_create(None)
    # Append 2 * max_turns + 5 turns; deque maxlen should clip.
    for i in range(2 * max_turns + 5):
        await store.append(session, _caregiver_turn(f"msg {i}"))
    assert len(session.turns) == max_turns * 2
    # Oldest dropped: earliest text remaining is "msg 5"
    assert session.turns[0].text == "msg 5"


# T006 -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_ttl_expired_session_yields_fresh_id() -> None:
    store, now = _make_store(ttl_seconds=60)
    s1 = await store.get_or_create(None)
    # Advance past TTL.
    now[0] = now[0] + timedelta(seconds=61)
    s2 = await store.get_or_create(s1.id)
    assert s2.id != s1.id
    # Old session no longer resident.
    assert store._peek(s1.id) is None


@pytest.mark.asyncio
async def test_ttl_within_window_keeps_session() -> None:
    store, now = _make_store(ttl_seconds=60)
    s1 = await store.get_or_create(None)
    now[0] = now[0] + timedelta(seconds=30)
    s2 = await store.get_or_create(s1.id)
    assert s2 is s1
    assert s2.last_activity_at == now[0]


# T007 -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_lru_evicts_least_recently_active_when_full() -> None:
    store, now = _make_store(max_sessions=3)
    s1 = await store.get_or_create(None)
    now[0] = now[0] + timedelta(seconds=1)
    s2 = await store.get_or_create(None)
    now[0] = now[0] + timedelta(seconds=1)
    s3 = await store.get_or_create(None)
    # Touch s1 to make it most-recent.
    now[0] = now[0] + timedelta(seconds=1)
    await store.get_or_create(s1.id)
    # Insert a fourth — s2 (oldest activity) must be evicted.
    now[0] = now[0] + timedelta(seconds=1)
    s4 = await store.get_or_create(None)
    assert store._resident_count() == 3
    assert store._peek(s2.id) is None
    assert store._peek(s1.id) is s1
    assert store._peek(s3.id) is s3
    assert store._peek(s4.id) is s4


# T008 -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_oversize_message_raises() -> None:
    store, _ = _make_store(message_max_bytes=16)
    session = await store.get_or_create(None)
    with pytest.raises(SessionMessageTooLargeError):
        await store.append(session, _caregiver_turn("x" * 17))


@pytest.mark.asyncio
async def test_max_byte_message_accepted() -> None:
    store, _ = _make_store(message_max_bytes=16)
    session = await store.get_or_create(None)
    await store.append(session, _caregiver_turn("x" * 16))
    assert len(session.turns) == 1


# T009 -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_per_session_lock_serializes_transactions() -> None:
    """Two concurrent transactions on the same session must not interleave."""
    store, _ = _make_store(max_turns=20)
    session = await store.get_or_create(None)

    timeline: list[tuple[str, str]] = []  # (event, owner)

    async def txn(owner: str) -> None:
        async with session.lock:
            timeline.append(("enter", owner))
            await asyncio.sleep(0.01)
            await store.append(session, _caregiver_turn(f"{owner}-1"))
            await asyncio.sleep(0.01)
            await store.append(session, _caregiver_turn(f"{owner}-2"))
            timeline.append(("exit", owner))

    await asyncio.gather(txn("A"), txn("B"))

    # No interleaving: every "enter X" is immediately followed by "exit X".
    pairs = [(timeline[i], timeline[i + 1]) for i in range(0, len(timeline), 2)]
    for enter, exit_ in pairs:
        assert enter[0] == "enter" and exit_[0] == "exit"
        assert enter[1] == exit_[1]


# T010 -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_recent_view_empty_session() -> None:
    store, _ = _make_store()
    session = await store.get_or_create(None)
    assert await store.recent_view(session, token_budget=1000) == []


@pytest.mark.asyncio
async def test_recent_view_returns_suffix_within_budget() -> None:
    store, _ = _make_store(max_turns=20, message_max_bytes=10_000)
    session = await store.get_or_create(None)
    # Each turn ~"x" * 80 chars => ~24 tokens per turn (80//4 + 4).
    turns = [_caregiver_turn("x" * 80, cid=f"c{i}") for i in range(10)]
    for t in turns:
        await store.append(session, t)
    per = _estimate_turn_tokens(turns[0])
    # Budget for ~3 turns.
    view = await store.recent_view(session, token_budget=per * 3)
    assert 1 <= len(view) <= 3
    # Must be the NEWEST turns (suffix), oldest first within the suffix.
    assert view == list(session.turns)[-len(view):]


@pytest.mark.asyncio
async def test_recent_view_full_history_when_budget_exceeds_total() -> None:
    store, _ = _make_store()
    session = await store.get_or_create(None)
    for i in range(5):
        await store.append(session, _caregiver_turn(f"msg {i}"))
    view = await store.recent_view(session, token_budget=1_000_000)
    assert len(view) == 5
    assert [t.text for t in view] == [f"msg {i}" for i in range(5)]
