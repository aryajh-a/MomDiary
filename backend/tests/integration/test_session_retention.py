"""T029 / US3: HTTP-driven retention tests for the in-memory SessionStore.

Verifies that bounded retention (FIFO turn cap, LRU session cap, TTL expiry)
holds when driven through the FastAPI POST /v1/entries pipeline — not just at
the unit level.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from momdiary.agents.session_store import InMemorySessionStore
from momdiary.api.dependencies import get_session_store
from momdiary.config import get_settings
from tests.conftest import ScriptedAgent


class _Clock:
    def __init__(self, start: datetime) -> None:
        self.current = start

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


@pytest_asyncio.fixture
async def retention_setup(
    configured_app: Any, scripted_agent: ScriptedAgent
) -> AsyncIterator[tuple[AsyncClient, InMemorySessionStore, _Clock]]:
    """Override the dependency with a small, clock-controlled store."""
    clock = _Clock(datetime(2026, 5, 16, 8, 0, 0, tzinfo=timezone.utc))
    settings = get_settings()
    store = InMemorySessionStore(
        ttl_seconds=settings.momdiary_session_ttl_seconds,
        max_turns=settings.momdiary_session_max_turns,
        max_sessions=settings.momdiary_session_max_sessions,
        message_max_bytes=settings.momdiary_session_message_max_bytes,
        now_fn=clock,
    )
    from momdiary.api.dependencies import get_agent_runner

    configured_app.dependency_overrides[get_session_store] = lambda: store
    configured_app.dependency_overrides[get_agent_runner] = lambda: scripted_agent
    async with AsyncClient(
        transport=ASGITransport(app=configured_app), base_url="http://test"
    ) as c:
        yield c, store, clock
    configured_app.dependency_overrides.clear()


def _script_log_feed(agent: ScriptedAgent, n: int) -> None:
    """Queue `n` log_feed calls — one per HTTP POST."""
    for i in range(n):
        agent.script(
            "log_feed",
            feed_type="formula",
            quantity=100 + i,
            unit="ml",
            occurred_at="2026-05-16T08:00:00-07:00",
        )


@pytest.mark.asyncio
async def test_fifo_cap_via_http(
    retention_setup: tuple[AsyncClient, InMemorySessionStore, _Clock],
    scripted_agent: ScriptedAgent,
) -> None:
    """Drive max_turns + 5 turns through one session → store cap holds at max_turns*2."""
    client, store, _clock = retention_setup
    max_turns = get_settings().momdiary_session_max_turns
    total_turns = max_turns + 5
    _script_log_feed(scripted_agent, total_turns)

    r0 = await client.post("/v1/entries", json={"message": "t0"})
    assert r0.status_code == 201, r0.text
    sid = r0.headers["X-Session-ID"]

    for i in range(1, total_turns):
        r = await client.post(
            "/v1/entries",
            json={"message": f"t{i}"},
            headers={"X-Session-ID": sid},
        )
        assert r.status_code == 201, r.text

    chat_session = store._sessions[sid]  # type: ignore[attr-defined]
    # Each HTTP call appends 2 turns (caregiver + assistant) → cap = max_turns*2.
    assert len(chat_session.turns) == max_turns * 2


@pytest.mark.asyncio
async def test_lru_eviction_via_http(
    retention_setup: tuple[AsyncClient, InMemorySessionStore, _Clock],
    scripted_agent: ScriptedAgent,
) -> None:
    """Create max_sessions+10 distinct sessions → resident count plateaus at max_sessions
    and the earliest sessions are evicted (LRU)."""
    client, store, _clock = retention_setup
    max_sessions = get_settings().momdiary_session_max_sessions
    overflow = 10
    total = max_sessions + overflow
    _script_log_feed(scripted_agent, total)

    created_ids: list[str] = []
    for i in range(total):
        r = await client.post("/v1/entries", json={"message": f"s{i}"})
        assert r.status_code == 201, r.text
        created_ids.append(r.headers["X-Session-ID"])

    assert len(store._sessions) == max_sessions  # type: ignore[attr-defined]
    # The first `overflow` sessions should have been evicted.
    for evicted in created_ids[:overflow]:
        assert evicted not in store._sessions  # type: ignore[attr-defined]
    # The last `max_sessions` should still be resident.
    for kept in created_ids[overflow:]:
        assert kept in store._sessions  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_ttl_via_clock(
    retention_setup: tuple[AsyncClient, InMemorySessionStore, _Clock],
    scripted_agent: ScriptedAgent,
) -> None:
    """Advance past TTL → next POST with the same X-Session-ID yields a fresh id."""
    client, store, clock = retention_setup
    scripted_agent.script(
        "log_feed",
        feed_type="breast_milk",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    ).script(
        "log_feed",
        feed_type="breast_milk",
        quantity=130,
        unit="ml",
        occurred_at="2026-05-16T09:00:00-07:00",
    )

    r1 = await client.post(
        "/v1/entries", json={"message": "120 ml breast milk now"}
    )
    assert r1.status_code == 201
    sid1 = r1.headers["X-Session-ID"]

    # Advance past TTL.
    clock.advance(get_settings().momdiary_session_ttl_seconds + 1)

    r2 = await client.post(
        "/v1/entries",
        json={"message": "130 ml breast milk now"},
        headers={"X-Session-ID": sid1},
    )
    assert r2.status_code == 201
    sid2 = r2.headers["X-Session-ID"]
    assert sid2 != sid1, "expired session must yield a fresh id"
    # And the expired session must be gone from the store.
    assert sid1 not in store._sessions  # type: ignore[attr-defined]
