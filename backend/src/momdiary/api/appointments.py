"""GET/PATCH/DELETE /v1/appointments — list + per-entry edit/delete + notes."""

from __future__ import annotations

from datetime import date as date_cls
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.auth.dependencies import ActiveBabyDep
from momdiary.db.engine import get_session
from momdiary.db.repositories.appointments import (
    AppointmentsRepository,
    AppointmentValidationError,
)
from momdiary.models.schemas import (
    AppointmentEntry,
    AppointmentListResponse,
    AppointmentNote,
    AppointmentNoteCreate,
    AppointmentUpdate,
)
from momdiary.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["appointments"])


def _to_iso(value) -> str:
    return value.isoformat(timespec="seconds") if hasattr(value, "isoformat") else str(value)


def _to_entry(r) -> AppointmentEntry:
    notes = [
        AppointmentNote.model_validate({"id": n.id, "body": n.body, "added_at": n.added_at})
        for n in r.notes
    ]
    return AppointmentEntry.model_validate(
        {
            "id": r.id,
            "scheduled_at": r.scheduled_at,
            "notes": [n.model_dump(mode="json") for n in notes],
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }
    )


@router.get("/appointments", response_model=AppointmentListResponse)
async def list_appointments(
    date: Annotated[date_cls, Query(description="Local calendar date.")],
    session: Annotated[AsyncSession, Depends(get_session)],
    baby: ActiveBabyDep,
) -> AppointmentListResponse:
    rows = await AppointmentsRepository(session).list_by_date(date)
    logger.info("appointments.list", date=date.isoformat(), baby_id=baby.id, count=len(rows))
    return AppointmentListResponse(
        date=date.isoformat(), items=[_to_entry(r) for r in rows]
    )


@router.patch("/appointments/{entry_id}", response_model=AppointmentEntry)
async def update_appointment(
    entry_id: Annotated[int, Path(ge=1)],
    body: AppointmentUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    baby: ActiveBabyDep,
) -> AppointmentEntry:
    repo = AppointmentsRepository(session)
    try:
        row, unchanged = await repo.update(
            entry_id,
            scheduled_at=_to_iso(body.scheduled_at) if body.scheduled_at is not None else None,
        )
    except AppointmentValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": str(exc)},
        ) from exc
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Appointment not found."},
        )
    await session.commit()
    logger.info(
        "appointments.patch", entry_id=entry_id, baby_id=baby.id, unchanged=unchanged
    )
    return _to_entry(row)


@router.delete("/appointments/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_appointment(
    entry_id: Annotated[int, Path(ge=1)],
    session: Annotated[AsyncSession, Depends(get_session)],
    baby: ActiveBabyDep,
) -> None:
    repo = AppointmentsRepository(session)
    row = await repo.soft_delete(entry_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Appointment not found."},
        )
    await session.commit()
    logger.info("appointments.delete", entry_id=entry_id, baby_id=baby.id)
    return None


@router.post("/appointments/{entry_id}/notes", response_model=AppointmentEntry, status_code=201)
async def add_appointment_note(
    entry_id: Annotated[int, Path(ge=1)],
    body: AppointmentNoteCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    baby: ActiveBabyDep,
) -> AppointmentEntry:
    repo = AppointmentsRepository(session)
    try:
        row = await repo.add_note(entry_id, body=body.body)
    except AppointmentValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": str(exc)},
        ) from exc
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Appointment not found."},
        )
    await session.commit()
    logger.info("appointments.note.add", entry_id=entry_id, baby_id=baby.id)
    return _to_entry(row)
