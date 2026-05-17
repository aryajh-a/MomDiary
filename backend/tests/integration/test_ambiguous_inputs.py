"""US3 ambiguous targets → clarification, no mutation (T053, SC-004)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.db.repositories.feeds import FeedsRepository
from tests.conftest import ScriptedAgent


@pytest.mark.asyncio
async def test_ambiguous_target_returns_clarification_no_mutation(
    client: AsyncClient, session: AsyncSession, scripted_agent: ScriptedAgent
) -> None:
    """FR-017 unambiguity rule: candidates returned, nothing changes."""
    repo = FeedsRepository(session)
    a = await repo.create(
        feed_type="formula",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    b = await repo.create(
        feed_type="formula",
        quantity=130,
        unit="ml",
        occurred_at="2026-05-16T11:00:00-07:00",
    )
    await session.commit()

    scripted_agent.script(
        "ask_for_clarification",
        question="Which morning feed did you mean?",
        suggested_candidates=[
            {"entry_type": "feed", "entry_id": a.id, "summary": "8 AM feed"},
            {"entry_type": "feed", "entry_id": b.id, "summary": "11 AM feed"},
        ],
    )
    r = await client.put(
        "/v1/entries",
        json={"message": "Correct the morning feed — it was 150 ml."},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["outcome"] == "clarification_requested"
    assert len(body["suggested_candidates"]) == 2

    # Verify no mutation
    feeds = (await client.get("/v1/feeds", params={"date": "2026-05-16"})).json()
    assert {f["id"]: f["quantity"] for f in feeds["items"]} == {
        a.id: 120.0,
        b.id: 130.0,
    }
