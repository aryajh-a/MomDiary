"""GET/PATCH/DELETE /v1/sleeps — date-scoped list + per-entry edit/delete."""

from __future__ import annotations

from datetime import date as date_cls
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.auth.dependencies import ActiveBabyDep, CurrentUserDep
from momdiary.db.engine import get_session
from momdiary.db.repositories.sleeps import (
    SleepsRepository,
    SleepValidationError,
    duration_minutes,
)
from momdiary.models.schemas import SleepCreate, SleepEntry, SleepListResponse, SleepUpdate
from momdiary.observability.logging import get_logger
from momdiary.services.time_service import get_user_timezone

logger = get_logger(__name__)

router = APIRouter(tags=["sleeps"])


def _to_iso(value) -> str:
    return value.isoformat(timespec="seconds") if hasattr(value, "isoformat") else str(value)


def _to_entry(r) -> SleepEntry:
    return SleepEntry.model_validate(
        {
            "id": r.id,
            "start_at": r.start_at,
            "end_at": r.end_at,
            "duration_minutes": duration_minutes(r),
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }
    )


@router.post("/sleeps", response_model=SleepEntry, status_code=status.HTTP_201_CREATED)
async def create_sleep(
    body: SleepCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    baby: ActiveBabyDep,
) -> SleepEntry:
    repo = SleepsRepository(session)
    try:
        row = await repo.create(
            start_at=_to_iso(body.start_at),
            end_at=_to_iso(body.end_at),
        )
    except SleepValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": str(exc)},
        ) from exc
    await session.commit()
    logger.info("sleeps.post", entry_id=row.id, baby_id=baby.id)
    return _to_entry(row)


@router.get("/sleeps", response_model=SleepListResponse)
async def list_sleeps(
    date: Annotated[date_cls, Query(description="Local calendar date.")],
    session: Annotated[AsyncSession, Depends(get_session)],
    auth: CurrentUserDep,
    baby: ActiveBabyDep,
) -> SleepListResponse:
    tz = await get_user_timezone(session, auth.user)
    rows = await SleepsRepository(session).list_by_start_date(date, tz)
    logger.info("sleeps.list", date=date.isoformat(), baby_id=baby.id, count=len(rows))
    return SleepListResponse(date=date.isoformat(), items=[_to_entry(r) for r in rows])


@router.patch("/sleeps/{entry_id}", response_model=SleepEntry)
async def update_sleep(
    entry_id: Annotated[int, Path(ge=1)],
    body: SleepUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    baby: ActiveBabyDep,
) -> SleepEntry:
    repo = SleepsRepository(session)
    try:
        row, unchanged = await repo.update(
            entry_id,
            start_at=_to_iso(body.start_at) if body.start_at is not None else None,
            end_at=_to_iso(body.end_at) if body.end_at is not None else None,
        )
    except SleepValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": str(exc)},
        ) from exc
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Sleep not found."},
        )
    await session.commit()
    logger.info("sleeps.patch", entry_id=entry_id, baby_id=baby.id, unchanged=unchanged)
    return _to_entry(row)


@router.delete(
    "/sleeps/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_sleep(
    entry_id: Annotated[int, Path(ge=1)],
    session: Annotated[AsyncSession, Depends(get_session)],
    baby: ActiveBabyDep,
) -> None:
    repo = SleepsRepository(session)
    row = await repo.soft_delete(entry_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Sleep not found."},
        )
    await session.commit()
    logger.info("sleeps.delete", entry_id=entry_id, baby_id=baby.id)
    return None
