"""Baby profile endpoints (feature 006)."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.auth.dependencies import CurrentUserDep, require_verified_email
from momdiary.babies.service import BabyService, GrowthSummary
from momdiary.db.engine import get_session
from momdiary.observability.logging import get_logger
from momdiary.observability.middleware import current_correlation_id
from momdiary.schemas.babies import (
    BabyCreate,
    BabyListResponse,
    BabyPublic,
    BabyUpdate,
)

router = APIRouter(tags=["babies"], prefix="/babies")
logger = get_logger(__name__)


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={
            "error": code,
            "message": message,
            "correlation_id": current_correlation_id() or "unknown",
        },
    )


def _public(baby, summary: GrowthSummary | None = None) -> BabyPublic:  # type: ignore[no-untyped-def]
    summary = summary or GrowthSummary()
    return BabyPublic(
        id=baby.id,
        owner_user_id=baby.owner_user_id,
        display_name=baby.display_name,
        date_of_birth=date.fromisoformat(baby.date_of_birth),
        color_tag=baby.color_tag,
        gender=baby.gender,
        weight_kg=baby.weight_kg,
        height_cm=baby.height_cm,
        last_measured_at=summary.last_measured_at,
        weight_kg_delta=summary.weight_kg_delta,
        height_cm_delta=summary.height_cm_delta,
        created_at=baby.created_at,
        updated_at=baby.updated_at,
    )


@router.get("", response_model=BabyListResponse)
async def list_babies(
    auth: CurrentUserDep,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> BabyListResponse:
    svc = BabyService(db)
    rows = await svc.list_for_user(auth.user.id)
    return BabyListResponse(
        items=[_public(b, await svc.growth_summary(b.id)) for b in rows]
    )


@router.post(
    "",
    response_model=BabyPublic,
    status_code=201,
    dependencies=[Depends(require_verified_email)],
)
async def create_baby(
    payload: BabyCreate,
    auth: CurrentUserDep,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> BabyPublic:
    svc = BabyService(db)
    baby = await svc.create(owner_user_id=auth.user.id, payload=payload)
    # Auto-activate the user's first baby (US2 / US3).
    if auth.user.active_baby_id is None:
        await svc.set_active(auth.user, baby)
    await db.commit()
    return _public(baby)


@router.patch(
    "/{baby_id}",
    response_model=BabyPublic,
    dependencies=[Depends(require_verified_email)],
)
async def update_baby(
    baby_id: int,
    payload: BabyUpdate,
    auth: CurrentUserDep,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> BabyPublic:
    svc = BabyService(db)
    baby = await svc.get_owned(auth.user.id, baby_id)
    if baby is None:
        raise _error(404, "not_found", "Baby not found.")
    baby = await svc.update(baby, payload)
    summary = await svc.growth_summary(baby.id)
    await db.commit()
    # FR-018: audit the edit with caregiver + baby + correlation id. Field
    # *names* only (no values) so no profile/credential material is logged.
    logger.info(
        "babies.patch",
        user_id=auth.user.id,
        baby_id=baby.id,
        fields=sorted(payload.model_fields_set),
        correlation_id=current_correlation_id() or "unknown",
    )
    return _public(baby, summary)


@router.delete("/{baby_id}", dependencies=[Depends(require_verified_email)])
async def delete_baby(
    baby_id: int,
    auth: CurrentUserDep,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, bool]:
    svc = BabyService(db)
    baby = await svc.get_owned(auth.user.id, baby_id)
    if baby is None:
        raise _error(404, "not_found", "Baby not found.")
    await svc.soft_delete(baby, owner=auth.user)
    await db.commit()
    return {"ok": True}
