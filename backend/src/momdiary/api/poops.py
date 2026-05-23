"""GET/PATCH/DELETE /v1/poops — date-scoped list + per-entry edit/delete."""

from __future__ import annotations

from datetime import date as date_cls
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.auth.dependencies import ActiveBabyDep
from momdiary.db.engine import get_session
from momdiary.db.repositories.poops import PoopsRepository, PoopValidationError
from momdiary.models.schemas import PoopCreate, PoopEntry, PoopListResponse, PoopUpdate
from momdiary.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["poops"])


def _to_iso(value) -> str:
    return value.isoformat(timespec="seconds") if hasattr(value, "isoformat") else str(value)


def _to_entry(r) -> PoopEntry:
    return PoopEntry.model_validate(
        {
            "id": r.id,
            "occurred_at": r.occurred_at,
            "consistency": r.consistency,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }
    )


@router.post("/poops", response_model=PoopEntry, status_code=status.HTTP_201_CREATED)
async def create_poop(
    body: PoopCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    baby: ActiveBabyDep,
) -> PoopEntry:
    repo = PoopsRepository(session)
    try:
        row = await repo.create(
            occurred_at=_to_iso(body.occurred_at),
            consistency=body.consistency,
        )
    except PoopValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": str(exc)},
        ) from exc
    await session.commit()
    logger.info("poops.post", entry_id=row.id, baby_id=baby.id)
    return _to_entry(row)


@router.get("/poops", response_model=PoopListResponse)
async def list_poops(
    date: Annotated[date_cls, Query(description="Local calendar date.")],
    session: Annotated[AsyncSession, Depends(get_session)],
    baby: ActiveBabyDep,
) -> PoopListResponse:
    rows = await PoopsRepository(session).list_by_date(date)
    logger.info("poops.list", date=date.isoformat(), baby_id=baby.id, count=len(rows))
    return PoopListResponse(date=date.isoformat(), items=[_to_entry(r) for r in rows])


@router.patch("/poops/{entry_id}", response_model=PoopEntry)
async def update_poop(
    entry_id: Annotated[int, Path(ge=1)],
    body: PoopUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    baby: ActiveBabyDep,
) -> PoopEntry:
    repo = PoopsRepository(session)
    try:
        row, unchanged = await repo.update(
            entry_id,
            occurred_at=_to_iso(body.occurred_at) if body.occurred_at is not None else None,
            consistency=body.consistency,
        )
    except PoopValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": str(exc)},
        ) from exc
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Poop not found."},
        )
    await session.commit()
    logger.info("poops.patch", entry_id=entry_id, baby_id=baby.id, unchanged=unchanged)
    return _to_entry(row)


@router.delete(
    "/poops/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_poop(
    entry_id: Annotated[int, Path(ge=1)],
    session: Annotated[AsyncSession, Depends(get_session)],
    baby: ActiveBabyDep,
) -> None:
    repo = PoopsRepository(session)
    row = await repo.soft_delete(entry_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Poop not found."},
        )
    await session.commit()
    logger.info("poops.delete", entry_id=entry_id, baby_id=baby.id)
    return None
