"""User profile endpoints — feature 008 (Clerk JWT)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.auth.dependencies import CurrentUserDep
from momdiary.babies.service import BabyService
from momdiary.db.engine import get_session
from momdiary.observability.middleware import current_correlation_id
from momdiary.schemas.auth import AuthSessionInfo, CurrentUserOut, UserPublic
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


def _public(user, *, email_verified: bool) -> UserPublic:  # type: ignore[no-untyped-def]
    return UserPublic(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        email_verified=email_verified,
        active_baby_id=user.active_baby_id,
    )


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@router.get("/me", response_model=CurrentUserOut)
async def get_me(current: CurrentUserDep) -> CurrentUserOut:
    """Return the authenticated caregiver projection (feature 008 contract)."""
    user = current.user
    return CurrentUserOut(
        id=user.id,
        clerk_user_id=user.clerk_user_id,
        email=user.email,
        email_verified=current.email_verified,
        display_name=user.display_name,
        active_baby_id=user.active_baby_id,
    )


async def _apply_profile_update(
    payload: UserUpdate,
    current,  # CurrentUser
    db: AsyncSession,
) -> AuthSessionInfo:
    user = current.user
    if payload.display_name != user.display_name:
        user.display_name = payload.display_name
        user.updated_at = _utcnow_iso()
        await db.commit()
    return AuthSessionInfo(user=_public(user, email_verified=current.email_verified))


@router.put("/me", response_model=AuthSessionInfo)
async def put_me(
    payload: UserUpdate,
    current: CurrentUserDep,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> AuthSessionInfo:
    """Profile mutation via bearer JWT. No `require_verified_email` gate
    (this is a profile field update, not a diary write — T046a)."""
    return await _apply_profile_update(payload, current, db)


@router.patch("/me", response_model=AuthSessionInfo)
async def patch_me(
    payload: UserUpdate,
    current: CurrentUserDep,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> AuthSessionInfo:
    return await _apply_profile_update(payload, current, db)


@router.post("/me/active-baby", response_model=AuthSessionInfo)
async def set_active_baby(
    payload: SetActiveBabyRequest,
    current: CurrentUserDep,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> AuthSessionInfo:
    svc = BabyService(db)
    baby = await svc.get_owned(current.user.id, payload.baby_id)
    if baby is None:
        raise _error(404, "not_found", "Baby not found.")
    await svc.set_active(current.user, baby)
    await db.commit()
    return AuthSessionInfo(
        user=_public(current.user, email_verified=current.email_verified)
    )
