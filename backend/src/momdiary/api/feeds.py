"""GET /v1/feeds — date-scoped list (T046)."""

from __future__ import annotations

from datetime import date as date_cls
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.db.engine import get_session
from momdiary.db.repositories.feeds import FeedsRepository
from momdiary.models.schemas import FeedEntry, FeedListResponse
from momdiary.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["feeds"])


@router.get("/feeds", response_model=FeedListResponse)
async def list_feeds(
    date: Annotated[date_cls, Query(description="Local calendar date.")],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FeedListResponse:
    rows = await FeedsRepository(session).list_by_date(date)
    logger.info("feeds.list", date=date.isoformat(), count=len(rows))
    items = [
        FeedEntry.model_validate(
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
        for r in rows
    ]
    return FeedListResponse(date=date.isoformat(), items=items)
