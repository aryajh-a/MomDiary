"""US3: appointment notes are append-only (T055, FR-006)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.db.repositories.appointments import AppointmentsRepository
from tests.conftest import ScriptedAgent


@pytest.mark.asyncio
async def test_add_note_appends_not_overwrites(
    client: AsyncClient, session: AsyncSession, scripted_agent: ScriptedAgent
) -> None:
    appt = await AppointmentsRepository(session).create_appointment(
        scheduled_at="2026-05-20T09:00:00-07:00", note="Bring records"
    )
    await session.commit()

    scripted_agent.script(
        "add_appointment_note",
        appointment_id=appt.id,
        body="Ask about shots",
    )
    r = await client.put(
        "/v1/entries", json={"message": "Add a note: ask about shots."}
    )
    assert r.status_code == 200, r.text
    bodies = [n["body"] for n in r.json()["entry"]["notes"]]
    assert bodies == ["Bring records", "Ask about shots"]
