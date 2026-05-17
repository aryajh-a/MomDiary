"""US3 soft delete hides from GETs (T056, FR-018)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.db.repositories.feeds import FeedsRepository
from tests.conftest import ScriptedAgent


@pytest.mark.asyncio
async def test_soft_delete_hides_from_gets_and_resolution(
    client: AsyncClient, session: AsyncSession, scripted_agent: ScriptedAgent
) -> None:
    row = await FeedsRepository(session).create(
        feed_type="formula",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    await session.commit()

    scripted_agent.script("delete_feed", entry_id=row.id)
    r = await client.put(
        "/v1/entries", json={"message": "Delete the 8am feed."}
    )
    assert r.status_code == 200
    assert r.json()["outcome"] == "deleted"

    feeds = (await client.get("/v1/feeds", params={"date": "2026-05-16"})).json()
    assert feeds["items"] == []

    # Subsequent explicit update via PUT must 404, not resurrect the row.
    again = await client.put(
        "/v1/entries",
        json={
            "message": "Restore that feed.",
            "entry_id": row.id,
            "entry_type": "feed",
        },
    )
    assert again.status_code == 404
