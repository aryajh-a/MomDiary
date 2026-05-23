"""Cross-tenant scoping integration tests for diary entries — feature 006 US3 (T038, T040)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.auth.context import set_active_baby_id
from momdiary.db.repositories.feeds import FeedsRepository


async def _seed_feed_for(session: AsyncSession, baby_id: int) -> int:
    """Create a feed scoped to the given baby_id and return its id."""
    set_active_baby_id(baby_id)
    repo = FeedsRepository(session)
    row = await repo.create(
        feed_type="formula",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    await session.commit()
    return row.id


@pytest.mark.asyncio
async def test_feeds_list_scoped_to_active_baby(
    anon_client: AsyncClient,
    session: AsyncSession,
    caregiver_factory,
) -> None:
    alice = await caregiver_factory(email="alice@scoping.com", baby_name="Alpha")
    bob = await caregiver_factory(email="bob@scoping.com", baby_name="Bravo")

    await _seed_feed_for(session, alice.baby_id)

    anon_client.cookies.set("momdiary_session", alice.session_token)
    r = await anon_client.get("/v1/feeds", params={"date": "2026-05-16"})
    assert r.status_code == 200, r.text
    assert len(r.json()["items"]) >= 1

    anon_client.cookies.clear()
    anon_client.cookies.set("momdiary_session", bob.session_token)
    r = await anon_client.get("/v1/feeds", params={"date": "2026-05-16"})
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_patch_other_caregivers_feed_returns_404(
    anon_client: AsyncClient,
    session: AsyncSession,
    caregiver_factory,
) -> None:
    alice = await caregiver_factory(email="alice@scope.com", baby_name="Alpha")
    bob = await caregiver_factory(email="bob@scope.com", baby_name="Bravo")
    entry_id = await _seed_feed_for(session, alice.baby_id)

    anon_client.cookies.set("momdiary_session", bob.session_token)
    r = await anon_client.patch(
        f"/v1/feeds/{entry_id}", json={"quantity": 200}
    )
    assert r.status_code == 404
    r = await anon_client.delete(f"/v1/feeds/{entry_id}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated_list_endpoint_returns_401(
    anon_client: AsyncClient,
) -> None:
    r = await anon_client.get("/v1/feeds", params={"date": "2026-05-16"})
    assert r.status_code == 401
    assert r.json()["error"] == "unauthenticated"
