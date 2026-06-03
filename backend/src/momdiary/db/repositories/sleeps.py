"""Repository for `sleeps` (FR-004, FR-008, FR-009, FR-015, FR-018)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.auth.context import get_active_baby_id, require_active_baby_id
from momdiary.models.orm import Sleep
from momdiary.observability.logging import get_logger
from momdiary.services.time_service import (
    date_window_in_tz,
    get_request_timezone,
    parse_iso_with_offset,
    to_iso,
    to_utc_iso,
)

logger = get_logger(__name__)


class SleepValidationError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _validate(start_at: str, end_at: str) -> tuple[datetime, datetime]:
    s = parse_iso_with_offset(start_at)
    e = parse_iso_with_offset(end_at)
    if s == e:
        raise SleepValidationError("end_at must differ from start_at")
    if e < s:
        raise SleepValidationError("end_at must be after start_at")
    return s, e


class SleepsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, start_at: str, end_at: str) -> Sleep:
        _validate(start_at, end_at)
        start_at = to_utc_iso(start_at)
        end_at = to_utc_iso(end_at)
        row = Sleep(
            baby_id=require_active_baby_id(),
            start_at=start_at,
            end_at=end_at,
            created_at=_now_iso(),
            updated_at=_now_iso(),
        )
        self._session.add(row)
        await self._session.flush()
        logger.info("sleeps.created", entry_id=row.id, start_at=start_at, end_at=end_at)
        return row

    async def get_by_id(self, entry_id: int, *, include_deleted: bool = False) -> Sleep | None:
        stmt = select(Sleep).where(Sleep.id == entry_id)
        baby_id = get_active_baby_id()
        if baby_id is not None:
            stmt = stmt.where(Sleep.baby_id == baby_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        if not include_deleted and row.deleted_at is not None:
            return None
        return row

    async def list_by_start_date(self, d: date) -> list[Sleep]:
        """FR-009: assign session to its start_at local date."""
        tz = await get_request_timezone(self._session)
        start, end = date_window_in_tz(d, tz)
        baby_id = require_active_baby_id()
        result = await self._session.execute(
            select(Sleep)
            .where(
                and_(
                    Sleep.baby_id == baby_id,
                    Sleep.deleted_at.is_(None),
                    Sleep.start_at >= to_iso(start),
                    Sleep.start_at < to_iso(end),
                )
            )
            .order_by(Sleep.start_at.asc(), Sleep.id.asc())
        )
        return list(result.scalars().all())

    async def update(
        self,
        entry_id: int,
        *,
        start_at: str | None = None,
        end_at: str | None = None,
    ) -> tuple[Sleep | None, bool]:
        row = await self.get_by_id(entry_id)
        if row is None:
            return None, False
        new_start = start_at if start_at is not None else row.start_at
        new_end = end_at if end_at is not None else row.end_at
        _validate(new_start, new_end)
        new_start = to_utc_iso(new_start)
        new_end = to_utc_iso(new_end)
        if new_start == row.start_at and new_end == row.end_at:
            logger.info("sleeps.update.unchanged", entry_id=entry_id)
            return row, True
        row.start_at = new_start
        row.end_at = new_end
        row.updated_at = _now_iso()
        await self._session.flush()
        logger.info("sleeps.updated", entry_id=entry_id)
        return row, False

    async def soft_delete(self, entry_id: int) -> Sleep | None:
        row = await self.get_by_id(entry_id)
        if row is None:
            logger.info("sleeps.soft_delete.miss", entry_id=entry_id)
            return None
        ts = _now_iso()
        row.deleted_at = ts
        row.updated_at = ts
        await self._session.flush()
        logger.info("sleeps.soft_deleted", entry_id=entry_id)
        return row


def duration_minutes(sleep: Sleep) -> int:
    s = parse_iso_with_offset(sleep.start_at)
    e = parse_iso_with_offset(sleep.end_at)
    return max(1, int((e - s).total_seconds() // 60))
