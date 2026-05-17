"""Integration tests for US2 GET-by-date (T036–T039)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.db.repositories.appointments import AppointmentsRepository
from momdiary.db.repositories.feeds import FeedsRepository
from momdiary.db.repositories.poops import PoopsRepository
from momdiary.db.repositories.sleeps import SleepsRepository


@pytest.mark.asyncio
async def test_feeds_by_date(client: AsyncClient, session: AsyncSession) -> None:
    repo = FeedsRepository(session)
    await repo.create(
        feed_type="formula",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    await repo.create(
        feed_type="formula",
        quantity=100,
        unit="ml",
        occurred_at="2026-05-16T12:00:00-07:00",
    )
    # Different date — should not appear
    await repo.create(
        feed_type="formula",
        quantity=90,
        unit="ml",
        occurred_at="2026-05-15T23:00:00-07:00",
    )
    await session.commit()

    r = await client.get("/v1/feeds", params={"date": "2026-05-16"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2
    assert items[0]["occurred_at"] < items[1]["occurred_at"]


@pytest.mark.asyncio
async def test_sleeps_spanning_midnight(
    client: AsyncClient, session: AsyncSession
) -> None:
    """FR-009: spanning sessions filed under start_at's local date."""
    repo = SleepsRepository(session)
    await repo.create(
        start_at="2026-05-16T23:30:00-07:00",
        end_at="2026-05-17T01:15:00-07:00",
    )
    await session.commit()

    r16 = await client.get("/v1/sleeps", params={"date": "2026-05-16"})
    r17 = await client.get("/v1/sleeps", params={"date": "2026-05-17"})
    assert len(r16.json()["items"]) == 1
    assert len(r17.json()["items"]) == 0


@pytest.mark.asyncio
async def test_empty_day_returns_200_with_empty_list(client: AsyncClient) -> None:
    r = await client.get("/v1/feeds", params={"date": "2026-05-16"})
    assert r.status_code == 200
    assert r.json() == {"date": "2026-05-16", "items": []}


@pytest.mark.asyncio
async def test_appointments_with_notes(
    client: AsyncClient, session: AsyncSession
) -> None:
    repo = AppointmentsRepository(session)
    appt = await repo.create_appointment(
        scheduled_at="2026-05-16T09:00:00-07:00", note="Bring records"
    )
    await repo.add_note(appt.id, body="Ask about shots")
    await session.commit()

    r = await client.get("/v1/appointments", params={"date": "2026-05-16"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert len(items[0]["notes"]) == 2


@pytest.mark.asyncio
async def test_poops_by_date(client: AsyncClient, session: AsyncSession) -> None:
    repo = PoopsRepository(session)
    await repo.create(occurred_at="2026-05-16T10:00:00-07:00", consistency="soft")
    await session.commit()
    r = await client.get("/v1/poops", params={"date": "2026-05-16"})
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1
