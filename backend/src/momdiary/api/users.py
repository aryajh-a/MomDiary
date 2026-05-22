"""User profile endpoints (feature 006)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.auth.dependencies import CurrentUserDep
from momdiary.babies.service import BabyService
from momdiary.db.engine import get_session
from momdiary.observability.middleware import current_correlation_id
from momdiary.schemas.auth import AuthSessionInfo, UserPublic
from momdiary.schemas.users import SetActiveBabyRequest, UserUpdate

router = APIRouter(tags=["users"], prefix="/users")


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={
            "error": code,
            "message": message,
            "correlation_id": current_correlation_id() or "unknown",
        },
    )


def _public(user) -> UserPublic:  # type: ignore[no-untyped-def]
    return UserPublic(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        active_baby_id=user.active_baby_id,
    )


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@router.patch("/me", response_model=AuthSessionInfo)
async def update_me(
    payload: UserUpdate,
    auth: CurrentUserDep,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> AuthSessionInfo:
    user = auth.user
    if payload.display_name != user.display_name:
        user.display_name = payload.display_name
        user.updated_at = _utcnow_iso()
        await db.commit()
    return AuthSessionInfo(user=_public(user))


@router.post("/me/active-baby", response_model=AuthSessionInfo)
async def set_active_baby(
    payload: SetActiveBabyRequest,
    auth: CurrentUserDep,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> AuthSessionInfo:
    svc = BabyService(db)
    baby = await svc.get_owned(auth.user.id, payload.baby_id)
    if baby is None:
        raise _error(404, "not_found", "Baby not found.")
    await svc.set_active(auth.user, baby)
    await db.commit()
    return AuthSessionInfo(user=_public(auth.user))
