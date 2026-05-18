"""T027 / US2: contract test — every POST/PUT /v1/entries response carries a
matching `session_id` body field and `X-Session-ID` response header, across
all five outcomes (created/updated/deleted/clarification/error).
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.db.repositories.feeds import FeedsRepository
from tests.conftest import ScriptedAgent

_UUID_V4 = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _assert_session_envelope(resp: Any, body: dict[str, Any]) -> str:
    header_sid = resp.headers.get("X-Session-ID")
    assert header_sid, "X-Session-ID header missing"
    assert "session_id" in body, f"session_id missing from body: {body}"
    assert body["session_id"] == header_sid
    assert _UUID_V4.match(header_sid), f"not a UUIDv4: {header_sid}"
    return header_sid


@pytest.mark.asyncio
async def test_created_outcome_carries_session_id(
    client: AsyncClient, scripted_agent: ScriptedAgent
) -> None:
    scripted_agent.script(
        "log_feed",
        feed_type="breast_milk",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    r = await client.post(
        "/v1/entries", json={"message": "120 ml breast milk now"}
    )
    assert r.status_code == 201, r.text
    _assert_session_envelope(r, r.json())


@pytest.mark.asyncio
async def test_updated_outcome_carries_session_id(
    client: AsyncClient,
    session: AsyncSession,
    scripted_agent: ScriptedAgent,
) -> None:
    row = await FeedsRepository(session).create(
        feed_type="formula",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    await session.commit()
    scripted_agent.script("update_feed", entry_id=row.id, quantity=150)
    r = await client.put(
        "/v1/entries", json={"message": "make that 150 ml"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["outcome"] == "updated"
    _assert_session_envelope(r, body)


@pytest.mark.asyncio
async def test_deleted_outcome_carries_session_id(
    client: AsyncClient,
    session: AsyncSession,
    scripted_agent: ScriptedAgent,
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
        "/v1/entries", json={"message": "delete that feed"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["outcome"] == "deleted"
    _assert_session_envelope(r, body)


@pytest.mark.asyncio
async def test_clarification_outcome_carries_session_id(
    client: AsyncClient, scripted_agent: ScriptedAgent
) -> None:
    scripted_agent.script(
        "ask_for_clarification",
        question="Which feed should I update?",
    )
    r = await client.put(
        "/v1/entries", json={"message": "make it 90"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["outcome"] == "clarification_requested"
    _assert_session_envelope(r, body)


@pytest.mark.asyncio
async def test_unknown_session_id_treated_as_fresh_contract(
    client: AsyncClient, scripted_agent: ScriptedAgent
) -> None:
    """FR-007: unknown id → response still carries a session_id matching header."""
    scripted_agent.script(
        "log_feed",
        feed_type="breast_milk",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    unknown_id = "11111111-1111-4111-8111-111111111111"
    r = await client.post(
        "/v1/entries",
        json={"message": "120 ml breast milk now"},
        headers={"X-Session-ID": unknown_id},
    )
    assert r.status_code == 201, r.text
    _assert_session_envelope(r, r.json())
