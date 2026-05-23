"""GET/PATCH/DELETE /v1/feeds — date-scoped list + per-entry edit/delete."""

from __future__ import annotations

from datetime import date as date_cls
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.auth.dependencies import ActiveBabyDep
from momdiary.db.engine import get_session
from momdiary.db.repositories.feeds import FeedsRepository, FeedValidationError
from momdiary.models.schemas import FeedCreate, FeedEntry, FeedListResponse, FeedUpdate
from momdiary.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["feeds"])


def _to_iso(value) -> str:
    return value.isoformat(timespec="seconds") if hasattr(value, "isoformat") else str(value)


def _to_entry(r) -> FeedEntry:
    return FeedEntry.model_validate(
        {
            "id": r.id,
            "feed_type": r.feed_type,
            "quantity": r.quantity,
            "unit": r.unit,
            "occurred_at": r.occurred_at,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }
    )


@router.post("/feeds", response_model=FeedEntry, status_code=status.HTTP_201_CREATED)
async def create_feed(
    body: FeedCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    baby: ActiveBabyDep,
) -> FeedEntry:
    repo = FeedsRepository(session)
    try:
        row = await repo.create(
            feed_type=body.feed_type,
            quantity=body.quantity,
            unit=body.unit,
            occurred_at=_to_iso(body.occurred_at),
        )
    except FeedValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": str(exc)},
        ) from exc
    await session.commit()
    logger.info("feeds.post", entry_id=row.id, baby_id=baby.id)
    return _to_entry(row)


@router.get("/feeds", response_model=FeedListResponse)
async def list_feeds(
    date: Annotated[date_cls, Query(description="Local calendar date.")],
    session: Annotated[AsyncSession, Depends(get_session)],
    baby: ActiveBabyDep,
) -> FeedListResponse:
    rows = await FeedsRepository(session).list_by_date(date)
    logger.info("feeds.list", date=date.isoformat(), baby_id=baby.id, count=len(rows))
    return FeedListResponse(date=date.isoformat(), items=[_to_entry(r) for r in rows])


@router.patch("/feeds/{entry_id}", response_model=FeedEntry)
async def update_feed(
    entry_id: Annotated[int, Path(ge=1)],
    body: FeedUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    baby: ActiveBabyDep,
) -> FeedEntry:
    repo = FeedsRepository(session)
    try:
        row, unchanged = await repo.update(
            entry_id,
            feed_type=body.feed_type,
            quantity=body.quantity,
            unit=body.unit,
            occurred_at=_to_iso(body.occurred_at) if body.occurred_at is not None else None,
        )
    except FeedValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": str(exc)},
        ) from exc
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Feed not found."},
        )
    await session.commit()
    logger.info("feeds.patch", entry_id=entry_id, baby_id=baby.id, unchanged=unchanged)
    return _to_entry(row)


@router.delete(
    "/feeds/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_feed(
    entry_id: Annotated[int, Path(ge=1)],
    session: Annotated[AsyncSession, Depends(get_session)],
    baby: ActiveBabyDep,
) -> None:
    repo = FeedsRepository(session)
    row = await repo.soft_delete(entry_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Feed not found."},
        )
    await session.commit()
    logger.info("feeds.delete", entry_id=entry_id, baby_id=baby.id)
    return None
