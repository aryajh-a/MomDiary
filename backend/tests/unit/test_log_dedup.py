"""Same-minute dedup in log_* tools auto-routes to update_* (replaces prompt Rule 5)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.agents.tools.feeds import log_feed
from momdiary.agents.tools.poops import log_poop
from momdiary.agents.tools.sleeps import log_sleep
from momdiary.agents.tools.appointments import log_appointment

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Feeds
# ---------------------------------------------------------------------------


async def test_log_feed_same_minute_routes_to_update(session: AsyncSession) -> None:
    first = await log_feed(
        session,
        feed_type="breast_milk",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    assert first.outcome == "created"

    same_minute = await log_feed(
        session,
        feed_type="formula",
        quantity=90,
        unit="ml",
        occurred_at="2026-05-16T08:00:45-07:00",  # +45s, same minute
    )
    assert same_minute.outcome == "updated"
    assert same_minute.entry_id == first.entry_id
    assert same_minute.payload["feed_type"] == "formula"
    assert same_minute.payload["quantity"] == 90


async def test_log_feed_different_minute_creates_new(session: AsyncSession) -> None:
    first = await log_feed(
        session,
        feed_type="breast_milk",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    second = await log_feed(
        session,
        feed_type="breast_milk",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:01:00-07:00",  # +60s, next minute
    )
    assert second.outcome == "created"
    assert second.entry_id != first.entry_id


async def test_log_feed_same_minute_across_offsets(session: AsyncSession) -> None:
    """Same absolute instant expressed with a different offset still dedups."""
    first = await log_feed(
        session,
        feed_type="breast_milk",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",  # 15:00:00 UTC
    )
    same_instant_other_offset = await log_feed(
        session,
        feed_type="formula",
        quantity=80,
        unit="ml",
        occurred_at="2026-05-16T15:00:30+00:00",  # same minute UTC
    )
    assert same_instant_other_offset.outcome == "updated"
    assert same_instant_other_offset.entry_id == first.entry_id


async def test_log_feed_dedup_identical_values_returns_unchanged(
    session: AsyncSession,
) -> None:
    first = await log_feed(
        session,
        feed_type="breast_milk",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    repeat = await log_feed(
        session,
        feed_type="breast_milk",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    assert repeat.outcome == "updated"
    assert repeat.entry_id == first.entry_id
    assert repeat.unchanged is True


# ---------------------------------------------------------------------------
# Sleeps
# ---------------------------------------------------------------------------


async def test_log_sleep_same_start_minute_routes_to_update(
    session: AsyncSession,
) -> None:
    first = await log_sleep(
        session,
        start_at="2026-05-16T13:00:00-07:00",
        end_at="2026-05-16T14:00:00-07:00",
    )
    assert first.outcome == "created"

    updated = await log_sleep(
        session,
        start_at="2026-05-16T13:00:30-07:00",  # same minute
        end_at="2026-05-16T14:30:00-07:00",
    )
    assert updated.outcome == "updated"
    assert updated.entry_id == first.entry_id


async def test_log_sleep_different_start_minute_creates_new(
    session: AsyncSession,
) -> None:
    first = await log_sleep(
        session,
        start_at="2026-05-16T13:00:00-07:00",
        end_at="2026-05-16T14:00:00-07:00",
    )
    second = await log_sleep(
        session,
        start_at="2026-05-16T15:00:00-07:00",
        end_at="2026-05-16T16:00:00-07:00",
    )
    assert second.outcome == "created"
    assert second.entry_id != first.entry_id


# ---------------------------------------------------------------------------
# Poops
# ---------------------------------------------------------------------------


async def test_log_poop_same_minute_routes_to_update(session: AsyncSession) -> None:
    first = await log_poop(
        session,
        occurred_at="2026-05-16T10:00:00-07:00",
        consistency="soft",
    )
    assert first.outcome == "created"

    updated = await log_poop(
        session,
        occurred_at="2026-05-16T10:00:20-07:00",  # same minute
        consistency="hard",
    )
    assert updated.outcome == "updated"
    assert updated.entry_id == first.entry_id
    assert updated.payload["consistency"] == "hard"


async def test_log_poop_different_minute_creates_new(session: AsyncSession) -> None:
    first = await log_poop(
        session,
        occurred_at="2026-05-16T10:00:00-07:00",
        consistency="soft",
    )
    second = await log_poop(
        session,
        occurred_at="2026-05-16T10:05:00-07:00",
        consistency="soft",
    )
    assert second.outcome == "created"
    assert second.entry_id != first.entry_id


# ---------------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------------


async def test_log_appointment_same_minute_no_note_returns_unchanged(
    session: AsyncSession,
) -> None:
    first = await log_appointment(
        session, scheduled_at="2026-05-20T09:00:00-07:00"
    )
    assert first.outcome == "created"

    again = await log_appointment(
        session, scheduled_at="2026-05-20T09:00:30-07:00"  # same minute
    )
    assert again.outcome == "updated"
    assert again.entry_id == first.entry_id
    assert again.unchanged is True


async def test_log_appointment_same_minute_with_note_appends(
    session: AsyncSession,
) -> None:
    first = await log_appointment(
        session,
        scheduled_at="2026-05-20T09:00:00-07:00",
        note="Bring vaccine record",
    )
    assert first.outcome == "created"
    assert len(first.payload["notes"]) == 1

    follow_up = await log_appointment(
        session,
        scheduled_at="2026-05-20T09:00:00-07:00",
        note="Also ask about sleep regression",
    )
    assert follow_up.outcome == "updated"
    assert follow_up.entry_id == first.entry_id
    assert follow_up.unchanged is False
    # Both notes are preserved (notes are append-only).
    bodies = [n["body"] for n in follow_up.payload["notes"]]
    assert "Bring vaccine record" in bodies
    assert "Also ask about sleep regression" in bodies


async def test_log_appointment_different_minute_creates_new(
    session: AsyncSession,
) -> None:
    first = await log_appointment(
        session, scheduled_at="2026-05-20T09:00:00-07:00"
    )
    second = await log_appointment(
        session, scheduled_at="2026-05-20T09:30:00-07:00"
    )
    assert second.outcome == "created"
    assert second.entry_id != first.entry_id


# ---------------------------------------------------------------------------
# Soft-deleted rows must NOT participate in dedup
# ---------------------------------------------------------------------------


async def test_log_feed_ignores_soft_deleted_same_minute(
    session: AsyncSession,
) -> None:
    from momdiary.db.repositories.feeds import FeedsRepository

    first = await log_feed(
        session,
        feed_type="breast_milk",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    repo = FeedsRepository(session)
    await repo.soft_delete(first.entry_id)

    second = await log_feed(
        session,
        feed_type="formula",
        quantity=90,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    assert second.outcome == "created"
    assert second.entry_id != first.entry_id
