"""Unit tests for chat session store partitioning by (user_id, baby_id) — feature 006 FR-017 (T024)."""

from __future__ import annotations

import pytest

from momdiary.agents.session_store import InMemorySessionStore


def _make_store() -> InMemorySessionStore:
    return InMemorySessionStore(
        ttl_seconds=3600,
        max_turns=10,
        max_sessions=100,
        message_max_bytes=4096,
    )


@pytest.mark.asyncio
async def test_same_session_id_different_users_get_distinct_sessions() -> None:
    store = _make_store()
    sid = "shared-session-id"
    a = await store.get_or_create(sid, user_id=1, baby_id=10)
    b = await store.get_or_create(sid, user_id=2, baby_id=10)
    assert b.id != a.id
    assert b.id != sid


@pytest.mark.asyncio
async def test_same_session_id_different_babies_get_distinct_sessions() -> None:
    store = _make_store()
    a = await store.get_or_create(None, user_id=1, baby_id=10)
    b = await store.get_or_create(a.id, user_id=1, baby_id=20)
    assert b.id != a.id


@pytest.mark.asyncio
async def test_same_user_and_baby_returns_same_session() -> None:
    store = _make_store()
    a = await store.get_or_create(None, user_id=1, baby_id=10)
    b = await store.get_or_create(a.id, user_id=1, baby_id=10)
    assert b.id == a.id


@pytest.mark.asyncio
async def test_partition_key_is_tuple_of_three() -> None:
    store = _make_store()
    s = await store.get_or_create(None, user_id=7, baby_id=42)
    keys = list(store._sessions.keys())
    assert any(k == (7, 42, s.id) for k in keys)
