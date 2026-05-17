"""GET /v1/sleeps — date-scoped list (T047, FR-009)."""

from __future__ import annotations

from datetime import date as date_cls
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.db.engine import get_session
from momdiary.db.repositories.sleeps import SleepsRepository, duration_minutes
from momdiary.models.schemas import SleepEntry, SleepListResponse
from momdiary.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["sleeps"])


@router.get("/sleeps", response_model=SleepListResponse)
async def list_sleeps(
    date: Annotated[date_cls, Query(description="Local calendar date.")],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SleepListResponse:
    rows = await SleepsRepository(session).list_by_start_date(date)
    logger.info("sleeps.list", date=date.isoformat(), count=len(rows))
    items = [
        SleepEntry.model_validate(
            {
                "id": r.id,
                "start_at": r.start_at,
                "end_at": r.end_at,
                "duration_minutes": duration_minutes(r),
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
        )
        for r in rows
    ]
    return SleepListResponse(date=date.isoformat(), items=items)
