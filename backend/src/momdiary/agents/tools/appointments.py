"""MAF tool implementations for `appointments` + notes."""

from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.agents.dispatcher import AgentRunResult
from momdiary.agents.tools._dedup import find_same_minute
from momdiary.db.repositories.appointments import AppointmentsRepository
from momdiary.models.orm import Appointment
from momdiary.models.schemas import AppointmentEntry, AppointmentNote
from momdiary.observability.logging import get_logger
from momdiary.services.time_service import (
    get_default_timezone,
    parse_iso_with_offset,
)

logger = get_logger(__name__)


def _to_entry(row: Appointment) -> dict:
    notes = [
        AppointmentNote.model_validate(
            {"id": n.id, "body": n.body, "added_at": n.added_at}
        )
        for n in (row.notes or [])
    ]
    return AppointmentEntry.model_validate(
        {
            "id": row.id,
            "scheduled_at": row.scheduled_at,
            "notes": [n.model_dump(mode="json") for n in notes],
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
    ).model_dump(mode="json")


class LogAppointmentArgs(BaseModel):
    scheduled_at: str
    note: str | None = Field(default=None, max_length=2000)


class UpdateAppointmentArgs(BaseModel):
    entry_id: int
    scheduled_at: str | None = None


class DeleteAppointmentArgs(BaseModel):
    entry_id: int


class AddAppointmentNoteArgs(BaseModel):
    appointment_id: int
    body: str = Field(min_length=1, max_length=2000)


async def log_appointment(
    session: AsyncSession, *, scheduled_at: str, note: str | None = None
) -> AgentRunResult:
    args = LogAppointmentArgs(scheduled_at=scheduled_at, note=note)
    repo = AppointmentsRepository(session)

    # Same-minute dedup -> route to update_appointment automatically. If
    # the caller supplied a note, append it (notes are append-only, per
    # the prompt's "never overwrite notes" rule).
    try:
        target_local_date = (
            parse_iso_with_offset(args.scheduled_at)
            .astimezone(await get_default_timezone(session))
            .date()
        )
        existing = await repo.list_by_date(target_local_date)
        dup = find_same_minute(existing, args.scheduled_at, lambda r: r.scheduled_at)
    except ValueError:
        dup = None

    if dup is not None:
        logger.info(
            "appointments.log.deduped_to_update",
            existing_id=dup.id,
            scheduled_at=args.scheduled_at,
            has_note=args.note is not None,
        )
        # Same-minute match: preserve the existing scheduled_at exactly
        # (no second-level overwrite). Only mutate state if a new note
        # was supplied — notes are append-only.
        if args.note is not None:
            row = await repo.add_note(dup.id, body=args.note)
            assert row is not None
            unchanged = False
            message = "Updated existing appointment and appended note."
        else:
            row = dup
            unchanged = True
            message = "No changes were needed."
        return AgentRunResult(
            selected_tool="log_appointment",
            outcome="updated",
            entry_type="appointment",
            entry_id=row.id,
            payload=_to_entry(row),
            agent_message=message,
            unchanged=unchanged,
        )

    row = await repo.create_appointment(
        scheduled_at=args.scheduled_at, note=args.note
    )
    return AgentRunResult(
        selected_tool="log_appointment",
        outcome="created",
        entry_type="appointment",
        entry_id=row.id,
        payload=_to_entry(row),
        agent_message="Appointment scheduled.",
    )


async def update_appointment(
    session: AsyncSession,
    *,
    entry_id: int,
    scheduled_at: str | None = None,
) -> AgentRunResult:
    args = UpdateAppointmentArgs(entry_id=entry_id, scheduled_at=scheduled_at)
    repo = AppointmentsRepository(session)
    row, unchanged = await repo.update(args.entry_id, scheduled_at=args.scheduled_at)
    if row is None:
        return AgentRunResult(
            selected_tool="update_appointment",
            outcome="rejected",
            entry_type="appointment",
            agent_message=f"Appointment {entry_id} not found.",
        )
    return AgentRunResult(
        selected_tool="update_appointment",
        outcome="updated",
        entry_type="appointment",
        entry_id=row.id,
        payload=_to_entry(row),
        agent_message=(
            "No changes were needed." if unchanged else "Appointment updated."
        ),
        unchanged=unchanged,
    )


async def delete_appointment(
    session: AsyncSession, *, entry_id: int
) -> AgentRunResult:
    repo = AppointmentsRepository(session)
    row = await repo.soft_delete(entry_id)
    if row is None:
        return AgentRunResult(
            selected_tool="delete_appointment",
            outcome="rejected",
            entry_type="appointment",
            agent_message=f"Appointment {entry_id} not found.",
        )
    return AgentRunResult(
        selected_tool="delete_appointment",
        outcome="deleted",
        entry_type="appointment",
        entry_id=row.id,
        payload=_to_entry(row),
        agent_message="Appointment removed.",
    )


async def add_appointment_note(
    session: AsyncSession, *, appointment_id: int, body: str
) -> AgentRunResult:
    args = AddAppointmentNoteArgs(appointment_id=appointment_id, body=body)
    repo = AppointmentsRepository(session)
    row = await repo.add_note(args.appointment_id, body=args.body)
    if row is None:
        return AgentRunResult(
            selected_tool="add_appointment_note",
            outcome="rejected",
            entry_type="appointment",
            agent_message=f"Appointment {appointment_id} not found.",
        )
    return AgentRunResult(
        selected_tool="add_appointment_note",
        outcome="updated",
        entry_type="appointment",
        entry_id=row.id,
        payload=_to_entry(row),
        agent_message="Note appended.",
    )
