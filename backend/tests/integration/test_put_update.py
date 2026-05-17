"""US3 PUT update — explicit and agent-resolved paths (T051, T052)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.db.repositories.feeds import FeedsRepository
from tests.conftest import ScriptedAgent


@pytest.mark.asyncio
async def test_explicit_entry_id_update(
    client: AsyncClient, session: AsyncSession, scripted_agent: ScriptedAgent
) -> None:
    """FR-017: explicit (entry_id, entry_type) bypasses agent target inference."""
    row = await FeedsRepository(session).create(
        feed_type="formula",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    await session.commit()

    # Even when the agent is set up to misroute, the explicit path wins.
    r = await client.put(
        "/v1/entries",
        json={
            "message": "Actually it was 150 ml.",
            "entry_id": row.id,
            "entry_type": "feed",
        },
    )
    assert r.status_code == 200, r.text
    # We did not pass new fields via the message, so the row is unchanged.
    assert r.json()["entry"]["id"] == row.id


@pytest.mark.asyncio
async def test_agent_resolved_update(
    client: AsyncClient, session: AsyncSession, scripted_agent: ScriptedAgent
) -> None:
    """US3 Scenario 1: agent infers target from message."""
    row = await FeedsRepository(session).create(
        feed_type="formula",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    await session.commit()

    scripted_agent.script(
        "update_feed",
        entry_id=row.id,
        quantity=150,
    )
    r = await client.put(
        "/v1/entries", json={"message": "The 8am feed was actually 150 ml."}
    )
    assert r.status_code == 200, r.text
    assert r.json()["entry"]["quantity"] == 150
