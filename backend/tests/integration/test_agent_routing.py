"""Integration tests for US1 agent routing (T023, T024)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import ScriptedAgent


@pytest.mark.asyncio
async def test_routes_each_event_type(
    client: AsyncClient, scripted_agent: ScriptedAgent
) -> None:
    """SC-001: each natural-language utterance maps to the right tool."""
    scripted_agent.script(
        "log_feed",
        feed_type="breast_milk",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    ).script(
        "log_sleep",
        start_at="2026-05-16T13:00:00-07:00",
        end_at="2026-05-16T14:30:00-07:00",
    ).script(
        "log_poop",
        occurred_at="2026-05-16T10:00:00-07:00",
        consistency="soft",
    ).script(
        "log_appointment",
        scheduled_at="2026-05-20T09:00:00-07:00",
    )

    r1 = await client.post(
        "/v1/entries", json={"message": "Baby drank 120 ml of breast milk at 8am."}
    )
    assert r1.status_code == 201, r1.text
    assert r1.json()["entry_type"] == "feed"

    r2 = await client.post(
        "/v1/entries", json={"message": "Baby napped from 1pm to 2:30pm."}
    )
    assert r2.status_code == 201
    assert r2.json()["entry_type"] == "sleep"
    assert r2.json()["entry"]["duration_minutes"] == 90

    r3 = await client.post(
        "/v1/entries", json={"message": "Soft poop around 10am."}
    )
    assert r3.status_code == 201
    assert r3.json()["entry_type"] == "poop"

    r4 = await client.post(
        "/v1/entries",
        json={"message": "Pediatrician appointment May 20 at 9am."},
    )
    assert r4.status_code == 201
    assert r4.json()["entry_type"] == "appointment"


@pytest.mark.asyncio
async def test_missing_required_field_triggers_clarification(
    client: AsyncClient, scripted_agent: ScriptedAgent
) -> None:
    """FR-011 / SC-004: ambiguous input → clarification, no entry persisted."""
    scripted_agent.script(
        "ask_for_clarification",
        question="What time did the feed happen?",
    )
    response = await client.post(
        "/v1/entries", json={"message": "Baby ate some formula."}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "clarification_requested"
    assert "time" in body["agent_message"].lower()

    feeds = await client.get("/v1/feeds", params={"date": "2026-05-16"})
    assert feeds.status_code == 200
    assert feeds.json()["items"] == []
