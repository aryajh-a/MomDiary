"""GET /v1/poops — date-scoped list (T048)."""

from __future__ import annotations

from datetime import date as date_cls
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.db.engine import get_session
from momdiary.db.repositories.poops import PoopsRepository
from momdiary.models.schemas import PoopEntry, PoopListResponse
from momdiary.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["poops"])


@router.get("/poops", response_model=PoopListResponse)
async def list_poops(
    date: Annotated[date_cls, Query(description="Local calendar date.")],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PoopListResponse:
    rows = await PoopsRepository(session).list_by_date(date)
    logger.info("poops.list", date=date.isoformat(), count=len(rows))
    items = [
        PoopEntry.model_validate(
            {
                "id": r.id,
                "occurred_at": r.occurred_at,
                "consistency": r.consistency,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
        )
        for r in rows
    ]
    return PoopListResponse(date=date.isoformat(), items=items)
