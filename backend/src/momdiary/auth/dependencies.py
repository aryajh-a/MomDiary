"""FastAPI auth dependencies — feature 008 (Clerk JWT).

Public surface:

* `get_current_user`  — verifies the bearer JWT, lazy-provisions the
  caregiver row on first sight, mirrors `email` + `email_verified_at`
  from the JWT claims, and returns a typed `CurrentUser`.
* `require_verified_email` — chained dependency that rejects callers
  whose primary email is not yet verified (FR-017). Use on every
  write endpoint; reads stay on `get_current_user` only.
* `AuthContext` / `CurrentUserDep` — legacy aliases retained so existing
  routes that imported them continue to type-check during the migration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.auth.clerk import ClerkAuthError, ClerkClaims, verify_clerk_jwt
from momdiary.auth.context import set_active_baby_id, set_active_user_timezone
from momdiary.db.engine import get_session
from momdiary.models.orm import Baby, User
from momdiary.observability.middleware import current_correlation_id
from momdiary.services.time_service import parse_zoneinfo_or_none


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={
            "error": code,
            "message": message,
            "correlation_id": current_correlation_id() or "unknown",
        },
    )


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """Typed projection of the authenticated caregiver."""

    user: User
    claims: ClerkClaims

    @property
    def id(self) -> int:
        return self.user.id

    @property
    def email_verified(self) -> bool:
        return self.claims.email_verified


# Legacy name retained so existing imports keep compiling.
AuthContext = CurrentUser


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise _error(401, "not_signed_in", "Authentication required.")
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise _error(401, "not_signed_in", "Malformed Authorization header.")
    return parts[1].strip()


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    """Resolve the caller via the `Authorization: Bearer <jwt>` header.

    Lazy-provisions a `users` row on first sight (FR-007); mirrors `email`
    and `email_verified_at` from the JWT claims on every call so a Clerk
    profile update propagates to MomDiary within one request.
    """
    token = _extract_bearer(authorization)
    try:
        claims = await verify_clerk_jwt(token)
    except ClerkAuthError as err:
        raise _error(401, "not_signed_in", err.message) from err

    user = (
        await db.execute(select(User).where(User.clerk_user_id == claims.sub))
    ).scalar_one_or_none()

    if user is None:
        user = User(
            clerk_user_id=claims.sub,
            email=claims.email,
            display_name=(claims.email.split("@", 1)[0] or "caregiver")[:80],
            email_verified_at=_utcnow_iso() if claims.email_verified else None,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        if user.deleted_at is not None:
            raise _error(401, "not_signed_in", "Account is no longer active.")
        mutated = False
        if user.email != claims.email:
            user.email = claims.email
            mutated = True
        had_verified = user.email_verified_at is not None
        if claims.email_verified and not had_verified:
            user.email_verified_at = _utcnow_iso()
            mutated = True
        elif (not claims.email_verified) and had_verified:
            user.email_verified_at = None
            mutated = True
        if mutated:
            user.updated_at = _utcnow_iso()
            await db.commit()

    # Feature 009: publish the caregiver's timezone for this request so
    # repositories and the agent resolve date windows in their zone.
    set_active_user_timezone(parse_zoneinfo_or_none(user.timezone))

    request.state.user_id = user.id
    request.state.clerk_user_id = claims.sub
    request.state.email_verified = claims.email_verified
    structlog.contextvars.bind_contextvars(
        user_id=user.id,
        clerk_user_id=claims.sub,
        email_verified=claims.email_verified,
        auth_mode="clerk_jwt",
    )
    return CurrentUser(user=user, claims=claims)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


async def require_verified_email(
    current: CurrentUserDep,
) -> CurrentUser:
    """Refuse callers whose primary email is not yet verified (FR-017)."""
    if not current.email_verified:
        raise _error(
            403,
            "email_not_verified",
            "Verify your email address before performing this action.",
        )
    return current


VerifiedUserDep = Annotated[CurrentUser, Depends(require_verified_email)]


async def require_active_baby(
    request: Request,
    current: CurrentUserDep,
    db: Annotated[AsyncSession, Depends(get_session)],
    x_active_baby_id: Annotated[str | None, Header()] = None,
) -> Baby:
    """Resolve the current request's active baby.

    Precedence:
      1. `X-Active-Baby-Id` header (per-request override).
      2. `users.active_baby_id` (persisted).
    Errors:
      * 409 `no_active_baby` if neither resolves.
      * 404 `not_found` if the requested baby isn't owned by the caller
        (FR-011: never leak cross-tenant existence).
    """
    user = current.user
    baby_id: int | None = None
    if x_active_baby_id is not None:
        try:
            baby_id = int(x_active_baby_id)
        except ValueError as err:
            raise _error(400, "invalid_input", "X-Active-Baby-Id must be an integer.") from err
    elif user.active_baby_id is not None:
        baby_id = user.active_baby_id

    if baby_id is None:
        raise _error(
            409,
            "no_active_baby",
            "No active baby selected. Create or select a baby first.",
        )

    stmt = select(Baby).where(
        Baby.id == baby_id,
        Baby.owner_user_id == user.id,
        Baby.deleted_at.is_(None),
    )
    baby = (await db.execute(stmt)).scalar_one_or_none()
    if baby is None:
        raise _error(404, "not_found", "Baby not found.")

    request.state.baby_id = baby.id
    set_active_baby_id(baby.id)
    structlog.contextvars.bind_contextvars(baby_id=baby.id)
    return baby


ActiveBabyDep = Annotated[Baby, Depends(require_active_baby)]


__all__ = [
    "ActiveBabyDep",
    "AuthContext",
    "CurrentUser",
    "CurrentUserDep",
    "VerifiedUserDep",
    "get_current_user",
    "require_active_baby",
    "require_verified_email",
]
