"""Unit tests for target resolver (T072)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.db.repositories.feeds import FeedsRepository
from momdiary.services.target_resolver import TargetCandidate, resolve


@pytest.mark.asyncio
async def test_single_explicit_match(session: AsyncSession) -> None:
    row = await FeedsRepository(session).create(
        feed_type="formula",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    await session.commit()
    r = await resolve(session, hinted_id=row.id, hinted_type="feed")
    assert r.is_resolved
    assert r.target is not None
    assert r.target.entry_id == row.id


@pytest.mark.asyncio
async def test_explicit_miss_returns_unresolved(session: AsyncSession) -> None:
    r = await resolve(session, hinted_id=999, hinted_type="feed")
    assert not r.is_resolved


@pytest.mark.asyncio
async def test_multi_candidate_returns_candidates(session: AsyncSession) -> None:
    cs = [
        TargetCandidate("feed", 1, "8 AM feed"),
        TargetCandidate("feed", 2, "11 AM feed"),
    ]
    r = await resolve(session, hinted_id=None, hinted_type=None, candidates=cs)
    assert not r.is_resolved
    assert len(r.candidates) == 2


@pytest.mark.asyncio
async def test_single_candidate_resolves(session: AsyncSession) -> None:
    cs = [TargetCandidate("feed", 42, "Only feed")]
    r = await resolve(session, hinted_id=None, hinted_type=None, candidates=cs)
    assert r.is_resolved
    assert r.target is not None
    assert r.target.entry_id == 42
