"""GET /v1/appointments — date-scoped list w/ notes (T049)."""

from __future__ import annotations

from datetime import date as date_cls
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.db.engine import get_session
from momdiary.db.repositories.appointments import AppointmentsRepository
from momdiary.models.schemas import (
    AppointmentEntry,
    AppointmentListResponse,
    AppointmentNote,
)
from momdiary.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["appointments"])


@router.get("/appointments", response_model=AppointmentListResponse)
async def list_appointments(
    date: Annotated[date_cls, Query(description="Local calendar date.")],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AppointmentListResponse:
    rows = await AppointmentsRepository(session).list_by_date(date)
    logger.info("appointments.list", date=date.isoformat(), count=len(rows))
    items: list[AppointmentEntry] = []
    for r in rows:
        notes = [
            AppointmentNote.model_validate(
                {"id": n.id, "body": n.body, "added_at": n.added_at}
            )
            for n in r.notes
        ]
        items.append(
            AppointmentEntry.model_validate(
                {
                    "id": r.id,
                    "scheduled_at": r.scheduled_at,
                    "notes": [n.model_dump(mode="json") for n in notes],
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
            )
        )
    return AppointmentListResponse(date=date.isoformat(), items=items)
