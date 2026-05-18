"""Benchmark: InMemorySessionStore recent_view + append cycle (T032).

Builds a 100-turn session and times one `recent_view → append → append` cycle.
Informational floor; the SC-006 50ms p95 budget is for the full HTTP path.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from momdiary.agents.session_store import ChatTurn, InMemorySessionStore


@pytest.mark.benchmark
def test_session_store_recent_view_and_append_under_5ms(benchmark) -> None:
    async def _setup() -> tuple[InMemorySessionStore, str]:
        store = InMemorySessionStore(
            ttl_seconds=86400,
            max_turns=100,
            max_sessions=100,
            message_max_bytes=4096,
        )
        chat_session = await store.get_or_create(None)
        now = datetime.now(timezone.utc)
        for i in range(100):
            await store.append(
                chat_session,
                ChatTurn(
                    role="caregiver" if i % 2 == 0 else "assistant",
                    text=f"turn {i} — " + "x" * 50,
                    correlation_id=f"cid-{i}",
                    created_at=now,
                ),
            )
        return store, chat_session.id

    store, sid = asyncio.new_event_loop().run_until_complete(_setup())

    async def _cycle() -> None:
        chat_session = await store.get_or_create(sid)
        await store.recent_view(chat_session, token_budget=12000)
        now = datetime.now(timezone.utc)
        await store.append(
            chat_session,
            ChatTurn(
                role="caregiver",
                text="follow-up",
                correlation_id="cid-bench",
                created_at=now,
            ),
        )
        await store.append(
            chat_session,
            ChatTurn(
                role="assistant",
                text="ok",
                correlation_id="cid-bench",
                created_at=now,
            ),
        )

    loop = asyncio.new_event_loop()

    def runner() -> None:
        loop.run_until_complete(_cycle())

    benchmark.pedantic(runner, rounds=20, iterations=1)
    stats = getattr(benchmark, "stats", None)
    if stats is not None and "median" in stats.stats:
        median_s = stats.stats["median"]
        assert median_s < 0.005, f"median={median_s}s exceeds 5ms floor"
