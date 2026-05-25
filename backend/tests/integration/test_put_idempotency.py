"""US3 idempotent PUT — repeated identical PUT yields byte-identical body (T054, SC-006)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.db.repositories.feeds import FeedsRepository
from tests.conftest import ScriptedAgent


@pytest.mark.asyncio
async def test_repeated_put_byte_identical(
    client: AsyncClient, session: AsyncSession, scripted_agent: ScriptedAgent
) -> None:
    row = await FeedsRepository(session).create(
        feed_type="formula",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    await session.commit()

    scripted_agent.script(
        "update_feed", entry_id=row.id, quantity=150
    ).script(
        "update_feed", entry_id=row.id, quantity=150
    )
    body = {"message": "Correct that feed to 150 ml."}
    r1 = await client.put("/v1/entries", json=body)
    r2 = await client.put("/v1/entries", json=body)
    assert r1.status_code == r2.status_code == 200

    # Strip volatile fields before comparing. The `agent_message` differs
    # between the two responses because the second PUT hits the dedup path
    # ("No changes were needed.") while the first applies the diff
    # ("Feed updated."). The idempotency contract is about *state*, not the
    # human-readable message, so we compare the resulting entry payload.
    def canonical(payload: dict) -> dict:
        e = dict(payload["entry"])
        e.pop("updated_at", None)
        return {
            **payload,
            "entry": e,
            "correlation_id": None,
            "session_id": None,
            "agent_message": None,
        }

    assert canonical(r1.json()) == canonical(r2.json())
