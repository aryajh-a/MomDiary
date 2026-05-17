"""SC-005: a full day with mixed entry types returns each entry exactly once (T040)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.db.repositories.appointments import AppointmentsRepository
from momdiary.db.repositories.feeds import FeedsRepository
from momdiary.db.repositories.poops import PoopsRepository
from momdiary.db.repositories.sleeps import SleepsRepository


@pytest.mark.asyncio
async def test_full_day_all_entries_returned_exactly_once(
    client: AsyncClient, session: AsyncSession
) -> None:
    feeds = FeedsRepository(session)
    sleeps = SleepsRepository(session)
    poops = PoopsRepository(session)
    appts = AppointmentsRepository(session)

    for h in range(8):  # 8 feeds
        await feeds.create(
            feed_type="formula",
            quantity=120,
            unit="ml",
            occurred_at=f"2026-05-16T{h + 6:02d}:00:00-07:00",
        )
    for h in range(6):  # 6 sleeps
        await sleeps.create(
            start_at=f"2026-05-16T{h * 3:02d}:30:00-07:00",
            end_at=f"2026-05-16T{h * 3 + 1:02d}:00:00-07:00",
        )
    for h in range(5):  # 5 poops
        await poops.create(
            occurred_at=f"2026-05-16T{h * 4 + 1:02d}:15:00-07:00",
            consistency="soft",
        )
    for h in range(2):  # 2 appointments
        await appts.create_appointment(
            scheduled_at=f"2026-05-16T{h * 6 + 9:02d}:00:00-07:00"
        )
    await session.commit()

    f = (await client.get("/v1/feeds", params={"date": "2026-05-16"})).json()
    s = (await client.get("/v1/sleeps", params={"date": "2026-05-16"})).json()
    p = (await client.get("/v1/poops", params={"date": "2026-05-16"})).json()
    a = (await client.get("/v1/appointments", params={"date": "2026-05-16"})).json()

    assert len(f["items"]) == 8
    assert len(s["items"]) == 6
    assert len(p["items"]) == 5
    assert len(a["items"]) == 2
    total = (
        len(f["items"]) + len(s["items"]) + len(p["items"]) + len(a["items"])
    )
    assert total == 21
    # No duplicates
    all_ids = (
        [("feed", x["id"]) for x in f["items"]]
        + [("sleep", x["id"]) for x in s["items"]]
        + [("poop", x["id"]) for x in p["items"]]
        + [("appointment", x["id"]) for x in a["items"]]
    )
    assert len(set(all_ids)) == len(all_ids)
