"""Read-only MAF tools: list entries for a given local date.

These tools never mutate state; they return a JSON-serializable dict
``{"date": "YYYY-MM-DD", "items": [...], "count": N}`` so the agent can
answer caregiver questions ("what feeds today?", "when did she last sleep?")
or resolve update/delete targets without a separate clarification round-trip.

Soft-deleted rows are excluded (FR-018) — list repositories already filter
them out.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.agents.tools import appointments as _appts
from momdiary.agents.tools import feeds as _feeds
from momdiary.agents.tools import poops as _poops
from momdiary.agents.tools import sleeps as _sleeps
from momdiary.db.repositories.appointments import AppointmentsRepository
from momdiary.db.repositories.feeds import FeedsRepository
from momdiary.db.repositories.poops import PoopsRepository
from momdiary.db.repositories.sleeps import SleepsRepository
from momdiary.services.time_service import get_request_timezone


class ListByDateArgs(BaseModel):
    """Shared argument schema for all four list_* tools."""

    date: str | None = None  # YYYY-MM-DD in the default local timezone; defaults to today


async def _resolve_date(session: AsyncSession, raw: str | None) -> _date:
    if raw is None or raw.strip() == "":
        tz = await get_request_timezone(session)
        return datetime.now(tz).date()
    # Accept "YYYY-MM-DD" strictly; let ValueError bubble up so the wrapper
    # can surface a useful error message to the model.
    return _date.fromisoformat(raw.strip())


def _envelope(d: _date, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"date": d.isoformat(), "count": len(items), "items": items}


async def list_feeds(session: AsyncSession, *, date: str | None = None) -> dict[str, Any]:
    d = await _resolve_date(session, date)
    rows = await FeedsRepository(session).list_by_date(d)
    return _envelope(d, [_feeds._to_entry(r) for r in rows])


async def list_sleeps(session: AsyncSession, *, date: str | None = None) -> dict[str, Any]:
    d = await _resolve_date(session, date)
    rows = await SleepsRepository(session).list_by_start_date(d)
    return _envelope(d, [_sleeps._to_entry(r) for r in rows])


async def list_poops(session: AsyncSession, *, date: str | None = None) -> dict[str, Any]:
    d = await _resolve_date(session, date)
    rows = await PoopsRepository(session).list_by_date(d)
    return _envelope(d, [_poops._to_entry(r) for r in rows])


async def list_appointments(
    session: AsyncSession, *, date: str | None = None
) -> dict[str, Any]:
    d = await _resolve_date(session, date)
    rows = await AppointmentsRepository(session).list_by_date(d)
    return _envelope(d, [_appts._to_entry(r) for r in rows])
