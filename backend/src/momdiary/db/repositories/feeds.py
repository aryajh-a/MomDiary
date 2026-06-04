"""Repository for `feeds` (FR-003, FR-008, FR-014, FR-015, FR-018)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.auth.context import get_active_baby_id, require_active_baby_id
from momdiary.models.orm import Feed
from momdiary.observability.logging import get_logger
from momdiary.services.time_service import (
    date_window_in_tz,
    get_request_timezone,
    parse_iso_with_offset,
    to_iso,
    to_utc_iso,
)

logger = get_logger(__name__)

ALLOWED_TYPES = {"breast_milk", "formula", "solids", "water"}
ALLOWED_UNITS = {"ml", "g"}


class FeedValidationError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _validate(feed_type: str, quantity: float, unit: str, occurred_at: str) -> datetime:
    if feed_type not in ALLOWED_TYPES:
        raise FeedValidationError(f"feed_type must be one of {ALLOWED_TYPES}")
    if quantity is None or quantity <= 0:
        raise FeedValidationError("quantity must be > 0")
    if unit not in ALLOWED_UNITS:
        raise FeedValidationError(f"unit must be one of {ALLOWED_UNITS}")
    occurred = parse_iso_with_offset(occurred_at)
    if occurred > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise FeedValidationError("occurred_at cannot be > now + 5 minutes")
    return occurred


class FeedsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, *, feed_type: str, quantity: float, unit: str, occurred_at: str
    ) -> Feed:
        _validate(feed_type, quantity, unit, occurred_at)
        occurred_at = to_utc_iso(occurred_at)
        row = Feed(
            baby_id=require_active_baby_id(),
            feed_type=feed_type,
            quantity=quantity,
            unit=unit,
            occurred_at=occurred_at,
            created_at=_now_iso(),
            updated_at=_now_iso(),
        )
        self._session.add(row)
        await self._session.flush()
        logger.info(
            "feeds.created",
            entry_id=row.id,
            feed_type=feed_type,
            quantity=quantity,
            unit=unit,
        )
        return row

    async def get_by_id(self, entry_id: int, *, include_deleted: bool = False) -> Feed | None:
        stmt = select(Feed).where(Feed.id == entry_id)
        baby_id = get_active_baby_id()
        if baby_id is not None:
            stmt = stmt.where(Feed.baby_id == baby_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        if not include_deleted and row.deleted_at is not None:
            return None
        return row

    async def list_by_date(self, d: date) -> list[Feed]:
        tz = await get_request_timezone(self._session)
        start, end = date_window_in_tz(d, tz)
        baby_id = require_active_baby_id()
        result = await self._session.execute(
            select(Feed)
            .where(
                and_(
                    Feed.baby_id == baby_id,
                    Feed.deleted_at.is_(None),
                    Feed.occurred_at >= to_iso(start),
                    Feed.occurred_at < to_iso(end),
                )
            )
            .order_by(Feed.occurred_at.asc(), Feed.id.asc())
        )
        return list(result.scalars().all())

    async def update(
        self,
        entry_id: int,
        *,
        feed_type: str | None = None,
        quantity: float | None = None,
        unit: str | None = None,
        occurred_at: str | None = None,
    ) -> tuple[Feed | None, bool]:
        """Returns `(row, unchanged)`. `unchanged=True` means no DB write (FR-015)."""
        row = await self.get_by_id(entry_id)
        if row is None:
            return None, False
        new_type = feed_type if feed_type is not None else row.feed_type
        new_qty = quantity if quantity is not None else row.quantity
        new_unit = unit if unit is not None else row.unit
        new_occ = occurred_at if occurred_at is not None else row.occurred_at
        _validate(new_type, new_qty, new_unit, new_occ)
        new_occ = to_utc_iso(new_occ)
        if (
            new_type == row.feed_type
            and new_qty == row.quantity
            and new_unit == row.unit
            and new_occ == row.occurred_at
        ):
            logger.info("feeds.update.unchanged", entry_id=entry_id)
            return row, True
        row.feed_type = new_type
        row.quantity = new_qty
        row.unit = new_unit
        row.occurred_at = new_occ
        row.updated_at = _now_iso()
        await self._session.flush()
        logger.info("feeds.updated", entry_id=entry_id)
        return row, False

    async def soft_delete(self, entry_id: int) -> Feed | None:
        row = await self.get_by_id(entry_id)
        if row is None:
            logger.info("feeds.soft_delete.miss", entry_id=entry_id)
            return None
        ts = _now_iso()
        row.deleted_at = ts
        row.updated_at = ts
        await self._session.flush()
        logger.info("feeds.soft_deleted", entry_id=entry_id)
        return row
