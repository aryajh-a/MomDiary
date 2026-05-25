"""Integration tests for US1 agent routing (T023, T024)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.db.repositories.appointments import AppointmentsRepository
from momdiary.db.repositories.feeds import FeedsRepository
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


# ---------------------------------------------------------------------------
# Per-tool create flows: assert payload shape, agent_message, side effects
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_feed_returns_full_entry_payload(
    client: AsyncClient, scripted_agent: ScriptedAgent
) -> None:
    """Successful feed create → 201, outcome=created, payload has all fields."""
    scripted_agent.script(
        "log_feed",
        feed_type="formula",
        quantity=90,
        unit="ml",
        occurred_at="2026-05-16T07:15:00-07:00",
    )
    r = await client.post(
        "/v1/entries", json={"message": "90 ml of formula at 7:15am."}
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["outcome"] == "created"
    assert body["entry_type"] == "feed"
    assert body["agent_message"] == "Logged 90.0 ml of formula."
    entry = body["entry"]
    # Schema (FeedEntry): id, feed_type, quantity, unit, occurred_at, created_at,
    # updated_at — must all be present in the response.
    for field in (
        "id",
        "feed_type",
        "quantity",
        "unit",
        "occurred_at",
        "created_at",
        "updated_at",
    ):
        assert field in entry, f"missing {field} in feed payload"
    assert entry["feed_type"] == "formula"
    assert entry["quantity"] == 90
    assert entry["unit"] == "ml"

    # The created row must be visible through the REST list endpoint.
    listed = await client.get("/v1/feeds", params={"date": "2026-05-16"})
    assert listed.status_code == 200
    assert [f["id"] for f in listed.json()["items"]] == [entry["id"]]


@pytest.mark.asyncio
async def test_log_sleep_computes_duration_minutes(
    client: AsyncClient, scripted_agent: ScriptedAgent
) -> None:
    scripted_agent.script(
        "log_sleep",
        start_at="2026-05-16T20:00:00-07:00",
        end_at="2026-05-16T22:45:00-07:00",
    )
    r = await client.post(
        "/v1/entries",
        json={"message": "Slept 8pm to 10:45pm."},
    )
    assert r.status_code == 201
    assert r.json()["entry_type"] == "sleep"
    assert r.json()["entry"]["duration_minutes"] == 165


@pytest.mark.asyncio
async def test_log_poop_persists_consistency(
    client: AsyncClient, scripted_agent: ScriptedAgent
) -> None:
    scripted_agent.script(
        "log_poop",
        occurred_at="2026-05-16T09:30:00-07:00",
        consistency="watery",
    )
    r = await client.post(
        "/v1/entries", json={"message": "Watery poop at 9:30am."}
    )
    assert r.status_code == 201
    assert r.json()["entry"]["consistency"] == "watery"


@pytest.mark.asyncio
async def test_log_appointment_with_note_field(
    client: AsyncClient, scripted_agent: ScriptedAgent
) -> None:
    scripted_agent.script(
        "log_appointment",
        scheduled_at="2026-05-25T10:00:00-07:00",
        note="Ask about sleep schedule",
    )
    r = await client.post(
        "/v1/entries",
        json={"message": "Pediatrician 5/25 10am, ask about sleep."},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["entry_type"] == "appointment"
    notes = body["entry"]["notes"]
    assert isinstance(notes, list)
    assert any(n["body"] == "Ask about sleep schedule" for n in notes)


# ---------------------------------------------------------------------------
# Direct-PUT update path (entry_id + entry_type hints bypass the model)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_with_hints_takes_direct_path_and_skips_agent(
    client: AsyncClient,
    session: AsyncSession,
    scripted_agent: ScriptedAgent,
) -> None:
    """When entry_id + entry_type are supplied, the agent is NOT invoked."""
    row = await FeedsRepository(session).create(
        feed_type="formula",
        quantity=100,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    await session.commit()

    # No scripted call queued — if the agent were invoked, this would raise.
    r = await client.put(
        "/v1/entries",
        json={
            "message": "Bump that to 130.",
            "entry_id": row.id,
            "entry_type": "feed",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["outcome"] == "updated"
    assert body["entry_type"] == "feed"
    # The scripted agent's call recorder confirms the dispatcher was never hit.
    assert scripted_agent.calls == []


@pytest.mark.asyncio
async def test_put_without_hints_uses_dispatcher(
    client: AsyncClient,
    session: AsyncSession,
    scripted_agent: ScriptedAgent,
) -> None:
    """PUT without entry_id/entry_type falls back to the model-routed path."""
    row = await FeedsRepository(session).create(
        feed_type="formula",
        quantity=100,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    await session.commit()

    scripted_agent.script(
        "update_feed",
        entry_id=row.id,
        quantity=140,
    )
    r = await client.put(
        "/v1/entries", json={"message": "Change that morning feed to 140."}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["outcome"] == "updated"
    assert body["entry"]["quantity"] == 140
    assert len(scripted_agent.calls) == 1
    assert scripted_agent.calls[0]["entry_id"] is None
    assert scripted_agent.calls[0]["entry_type"] is None


@pytest.mark.asyncio
async def test_put_direct_path_404_when_entry_missing(
    client: AsyncClient, scripted_agent: ScriptedAgent
) -> None:
    r = await client.put(
        "/v1/entries",
        json={
            "message": "Update it.",
            "entry_id": 99999,
            "entry_type": "feed",
        },
    )
    assert r.status_code == 404
    # The custom HTTPException handler renders dict-detail directly as the
    # response body (no `detail` wrapper).
    body = r.json()
    assert body["error"] == "not_found"
    # The agent must not have been invoked for an unresolved target.
    assert scripted_agent.calls == []


@pytest.mark.asyncio
async def test_put_direct_path_rejects_unknown_entry_type(
    client: AsyncClient,
) -> None:
    # `entry_type` is a Literal on AgentWriteRequest, so pydantic rejects the
    # value at request-parse time with a 422 (not the in-handler 400 path).
    r = await client.put(
        "/v1/entries",
        json={
            "message": "Update it.",
            "entry_id": 1,
            "entry_type": "not_a_real_type",
        },
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Delete via the dispatcher
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_feed_via_dispatcher(
    client: AsyncClient,
    session: AsyncSession,
    scripted_agent: ScriptedAgent,
) -> None:
    row = await FeedsRepository(session).create(
        feed_type="formula",
        quantity=100,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    await session.commit()

    scripted_agent.script("delete_feed", entry_id=row.id)
    r = await client.put(
        "/v1/entries", json={"message": "Actually drop that morning feed."}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["outcome"] == "deleted"
    assert body["entry_type"] == "feed"
    assert body["entry"]["id"] == row.id

    listed = await client.get("/v1/feeds", params={"date": "2026-05-16"})
    assert listed.json()["items"] == []


# ---------------------------------------------------------------------------
# Rejected outcomes — map onto 400 (no id) and 404 (with id)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rejected_without_entry_id_returns_400(
    client: AsyncClient, scripted_agent: ScriptedAgent
) -> None:
    # `update_feed` against a non-existent row → rejected w/o entry_id on
    # the result; the envelope maps that to a 400 validation error.
    scripted_agent.script("update_feed", entry_id=999999, quantity=50)
    r = await client.post(
        "/v1/entries", json={"message": "Change that feed to 50."}
    )
    assert r.status_code == 400
    assert r.json()["error"] == "validation_error"


# ---------------------------------------------------------------------------
# Dedup behavior: log_* with a same-minute existing row → outcome=updated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_feed_dedups_to_existing_same_minute_entry(
    client: AsyncClient,
    session: AsyncSession,
    scripted_agent: ScriptedAgent,
) -> None:
    """Rule 5 dedup: logging a feed at the same minute updates the existing
    row in place rather than creating a duplicate."""
    existing = await FeedsRepository(session).create(
        feed_type="formula",
        quantity=100,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    await session.commit()

    scripted_agent.script(
        "log_feed",
        feed_type="formula",
        quantity=130,  # bumped quantity, same minute
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    r = await client.post(
        "/v1/entries", json={"message": "Actually 130 ml at 8am."}
    )
    assert r.status_code == 200  # updated, not 201 created
    body = r.json()
    assert body["outcome"] == "updated"
    assert body["entry"]["id"] == existing.id
    assert body["entry"]["quantity"] == 130

    listed = await client.get("/v1/feeds", params={"date": "2026-05-16"})
    assert len(listed.json()["items"]) == 1


# ---------------------------------------------------------------------------
# Session continuity, history threading, correlation id, response headers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_response_carries_session_id_header_and_body(
    client: AsyncClient, scripted_agent: ScriptedAgent
) -> None:
    scripted_agent.script(
        "log_feed",
        feed_type="formula",
        quantity=80,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    r = await client.post("/v1/entries", json={"message": "80 ml formula 8am."})
    assert r.status_code == 201
    sid = r.headers.get("X-Session-ID")
    assert sid is not None and len(sid) > 0
    assert r.json()["session_id"] == sid


@pytest.mark.asyncio
async def test_session_id_reused_when_client_resends_header(
    client: AsyncClient, scripted_agent: ScriptedAgent
) -> None:
    scripted_agent.script(
        "log_feed",
        feed_type="formula",
        quantity=80,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    ).script(
        "log_feed",
        feed_type="formula",
        quantity=90,
        unit="ml",
        occurred_at="2026-05-16T11:00:00-07:00",
    )

    r1 = await client.post(
        "/v1/entries", json={"message": "80 ml formula 8am."}
    )
    sid = r1.headers["X-Session-ID"]
    r2 = await client.post(
        "/v1/entries",
        json={"message": "90 ml formula 11am."},
        headers={"X-Session-ID": sid},
    )
    assert r2.headers["X-Session-ID"] == sid
    assert r2.json()["session_id"] == sid

    # The second dispatch should have seen the first caregiver turn in history.
    second_call_history = scripted_agent.calls[1]["history"]
    assert any(
        getattr(t, "role", None) == "caregiver"
        and "80 ml formula 8am." in getattr(t, "text", "")
        for t in second_call_history
    )


@pytest.mark.asyncio
async def test_caller_correlation_id_is_echoed(
    client: AsyncClient, scripted_agent: ScriptedAgent
) -> None:
    scripted_agent.script(
        "log_feed",
        feed_type="formula",
        quantity=80,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    r = await client.post(
        "/v1/entries",
        json={"message": "80 ml formula 8am.", "correlation_id": "abc-123"},
    )
    assert r.status_code == 201
    assert r.json()["correlation_id"] == "abc-123"
    assert scripted_agent.calls[0]["correlation_id"] == "abc-123"


@pytest.mark.asyncio
async def test_hinted_entry_type_passed_to_dispatcher(
    client: AsyncClient, scripted_agent: ScriptedAgent
) -> None:
    """The model gets the caller-provided `entry_type` hint."""
    scripted_agent.script(
        "log_feed",
        feed_type="formula",
        quantity=80,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    r = await client.post(
        "/v1/entries",
        json={"message": "80 ml at 8am.", "entry_type": "feed"},
    )
    assert r.status_code == 201
    assert scripted_agent.calls[0]["entry_type"] == "feed"


# ---------------------------------------------------------------------------
# add_appointment_note (Rule 7 — bind doctor questions to an appointment)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_appointment_note_appends_to_existing(
    client: AsyncClient,
    session: AsyncSession,
    scripted_agent: ScriptedAgent,
) -> None:
    appt = await AppointmentsRepository(session).create_appointment(
        scheduled_at="2026-05-25T10:00:00-07:00",
        note="Initial visit",
    )
    await session.commit()

    scripted_agent.script(
        "add_appointment_note",
        appointment_id=appt.id,
        body="Ask about formula amount",
    )
    r = await client.post(
        "/v1/entries",
        json={"message": "Add a question for the doctor about formula amount."},
    )
    assert r.status_code == 200  # updated, not 201
    body = r.json()
    assert body["outcome"] == "updated"
    assert body["entry_type"] == "appointment"
    note_bodies = [n["body"] for n in body["entry"]["notes"]]
    assert "Ask about formula amount" in note_bodies
    assert "Initial visit" in note_bodies  # original preserved
