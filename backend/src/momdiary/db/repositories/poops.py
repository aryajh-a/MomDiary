"""Repository for `poops` (FR-005, FR-008, FR-015, FR-018)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.auth.context import get_active_baby_id, require_active_baby_id
from momdiary.models.orm import Poop
from momdiary.observability.logging import get_logger
from momdiary.services.time_service import (
    date_window_in_tz,
    get_request_timezone,
    parse_iso_with_offset,
    to_iso,
    to_utc_iso,
)

logger = get_logger(__name__)

ALLOWED_CONSISTENCY = {"watery", "soft", "formed", "hard"}


class PoopValidationError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _validate(occurred_at: str, consistency: str) -> None:
    if consistency not in ALLOWED_CONSISTENCY:
        raise PoopValidationError(f"consistency must be one of {ALLOWED_CONSISTENCY}")
    parse_iso_with_offset(occurred_at)


class PoopsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, occurred_at: str, consistency: str) -> Poop:
        _validate(occurred_at, consistency)
        occurred_at = to_utc_iso(occurred_at)
        row = Poop(
            baby_id=require_active_baby_id(),
            occurred_at=occurred_at,
            consistency=consistency,
            created_at=_now_iso(),
            updated_at=_now_iso(),
        )
        self._session.add(row)
        await self._session.flush()
        logger.info("poops.created", entry_id=row.id, consistency=consistency)
        return row

    async def get_by_id(self, entry_id: int, *, include_deleted: bool = False) -> Poop | None:
        stmt = select(Poop).where(Poop.id == entry_id)
        baby_id = get_active_baby_id()
        if baby_id is not None:
            stmt = stmt.where(Poop.baby_id == baby_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        if not include_deleted and row.deleted_at is not None:
            return None
        return row

    async def list_by_date(self, d: date) -> list[Poop]:
        tz = await get_request_timezone(self._session)
        start, end = date_window_in_tz(d, tz)
        baby_id = require_active_baby_id()
        result = await self._session.execute(
            select(Poop)
            .where(
                and_(
                    Poop.baby_id == baby_id,
                    Poop.deleted_at.is_(None),
                    Poop.occurred_at >= to_iso(start),
                    Poop.occurred_at < to_iso(end),
                )
            )
            .order_by(Poop.occurred_at.asc(), Poop.id.asc())
        )
        return list(result.scalars().all())

    async def update(
        self,
        entry_id: int,
        *,
        occurred_at: str | None = None,
        consistency: str | None = None,
    ) -> tuple[Poop | None, bool]:
        row = await self.get_by_id(entry_id)
        if row is None:
            return None, False
        new_occ = occurred_at if occurred_at is not None else row.occurred_at
        new_con = consistency if consistency is not None else row.consistency
        _validate(new_occ, new_con)
        new_occ = to_utc_iso(new_occ)
        if new_occ == row.occurred_at and new_con == row.consistency:
            logger.info("poops.update.unchanged", entry_id=entry_id)
            return row, True
        row.occurred_at = new_occ
        row.consistency = new_con
        row.updated_at = _now_iso()
        await self._session.flush()
        logger.info("poops.updated", entry_id=entry_id)
        return row, False

    async def soft_delete(self, entry_id: int) -> Poop | None:
        row = await self.get_by_id(entry_id)
        if row is None:
            logger.info("poops.soft_delete.miss", entry_id=entry_id)
            return None
        ts = _now_iso()
        row.deleted_at = ts
        row.updated_at = ts
        await self._session.flush()
        logger.info("poops.soft_deleted", entry_id=entry_id)
        return row
