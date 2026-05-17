"""Repository for `appointments` + `appointment_notes` (FR-006)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from momdiary.models.orm import Appointment, AppointmentNote
from momdiary.observability.logging import get_logger
from momdiary.services.time_service import (
    date_window_in_tz,
    get_default_timezone,
    parse_iso_with_offset,
    to_iso,
)

logger = get_logger(__name__)


class AppointmentValidationError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _validate(scheduled_at: str) -> None:
    parse_iso_with_offset(scheduled_at)


def _validate_note(body: str) -> None:
    if not body or not body.strip():
        raise AppointmentValidationError("note body is required")
    if len(body) > 2000:
        raise AppointmentValidationError("note body must be <= 2000 chars")


class AppointmentsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_appointment(
        self, *, scheduled_at: str, note: str | None = None
    ) -> Appointment:
        _validate(scheduled_at)
        if note is not None:
            _validate_note(note)
        row = Appointment(
            scheduled_at=scheduled_at,
            created_at=_now_iso(),
            updated_at=_now_iso(),
        )
        self._session.add(row)
        await self._session.flush()
        if note is not None:
            n = AppointmentNote(
                appointment_id=row.id, body=note, added_at=_now_iso()
            )
            self._session.add(n)
            await self._session.flush()
            await self._session.refresh(row, ["notes"])
        logger.info(
            "appointments.created",
            entry_id=row.id,
            scheduled_at=scheduled_at,
            has_note=note is not None,
        )
        return row

    async def get_by_id_with_notes(
        self, entry_id: int, *, include_deleted: bool = False
    ) -> Appointment | None:
        result = await self._session.execute(
            select(Appointment)
            .options(selectinload(Appointment.notes))
            .where(Appointment.id == entry_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        if not include_deleted and row.deleted_at is not None:
            return None
        return row

    async def list_by_date(self, d: date) -> list[Appointment]:
        tz = await get_default_timezone(self._session)
        start, end = date_window_in_tz(d, tz)
        result = await self._session.execute(
            select(Appointment)
            .options(selectinload(Appointment.notes))
            .where(
                and_(
                    Appointment.deleted_at.is_(None),
                    Appointment.scheduled_at >= to_iso(start),
                    Appointment.scheduled_at < to_iso(end),
                )
            )
            .order_by(Appointment.scheduled_at.asc(), Appointment.id.asc())
        )
        return list(result.scalars().all())

    async def update(
        self, entry_id: int, *, scheduled_at: str | None = None
    ) -> tuple[Appointment | None, bool]:
        row = await self.get_by_id_with_notes(entry_id)
        if row is None:
            return None, False
        new_sched = scheduled_at if scheduled_at is not None else row.scheduled_at
        _validate(new_sched)
        if new_sched == row.scheduled_at:
            logger.info("appointments.update.unchanged", entry_id=entry_id)
            return row, True
        row.scheduled_at = new_sched
        row.updated_at = _now_iso()
        await self._session.flush()
        logger.info("appointments.updated", entry_id=entry_id)
        return row, False

    async def soft_delete(self, entry_id: int) -> Appointment | None:
        row = await self.get_by_id_with_notes(entry_id)
        if row is None:
            logger.info("appointments.soft_delete.miss", entry_id=entry_id)
            return None
        ts = _now_iso()
        row.deleted_at = ts
        row.updated_at = ts
        await self._session.flush()
        logger.info("appointments.soft_deleted", entry_id=entry_id)
        return row

    async def add_note(self, appointment_id: int, *, body: str) -> Appointment | None:
        row = await self.get_by_id_with_notes(appointment_id)
        if row is None:
            logger.info("appointments.note.miss", appointment_id=appointment_id)
            return None
        _validate_note(body)
        note = AppointmentNote(
            appointment_id=row.id, body=body, added_at=_now_iso()
        )
        self._session.add(note)
        await self._session.flush()
        await self._session.refresh(row, ["notes"])
        logger.info(
            "appointments.note.added",
            appointment_id=appointment_id,
            note_id=note.id,
            total_notes=len(row.notes),
        )
        return row
