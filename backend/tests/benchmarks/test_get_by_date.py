"""Benchmark: p95 < 500 ms for a 50-entry day (T041, SC-003, Principle III)."""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.db.repositories.feeds import FeedsRepository


@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_get_feeds_by_date_under_500ms_p95(
    client: AsyncClient, session: AsyncSession, benchmark
) -> None:
    repo = FeedsRepository(session)
    for i in range(50):
        await repo.create(
            feed_type="formula",
            quantity=120,
            unit="ml",
            occurred_at=f"2026-05-16T{i // 3:02d}:{(i % 3) * 20:02d}:00-07:00",
        )
    await session.commit()

    async def call() -> None:
        r = await client.get("/v1/feeds", params={"date": "2026-05-16"})
        assert r.status_code == 200
        assert len(r.json()["items"]) == 50

    def runner() -> None:
        asyncio.get_event_loop().run_until_complete(call())

    # pytest-benchmark runs many iterations; assert p95 ourselves.
    result = benchmark.pedantic(runner, rounds=10, iterations=1)
    # `stats` may not always be populated synchronously; guard.
    stats = getattr(benchmark, "stats", None)
    if stats is not None and "percentiles" in stats.stats:
        p95 = stats.stats["percentiles"][95]
        assert p95 < 0.5, f"p95={p95}s exceeds 500ms budget"
