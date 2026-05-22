"""FastAPI auth dependencies — feature 006."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.auth.sessions import SessionService
from momdiary.config import get_settings
from momdiary.db.engine import get_session
from momdiary.models.orm import Baby, User
from momdiary.observability.middleware import current_correlation_id

from momdiary.auth.context import set_active_baby_id


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
class AuthContext:
    user: User
    session_token: str


async def current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    momdiary_session: Annotated[str | None, Cookie()] = None,
) -> AuthContext:
    """Resolve the caller via the `momdiary_session` cookie.

    Returns 401 unauthenticated when the cookie is missing, invalid, revoked,
    or expired. On success, slides the session's `expires_at` forward (rolling
    30 d) and stashes user/session info on `request.state` for the log
    enrichment middleware.
    """
    settings = get_settings()
    cookie_name = settings.momdiary_session_cookie_name
    token = momdiary_session if cookie_name == "momdiary_session" else (
        request.cookies.get(cookie_name)
    )
    if not token:
        raise _error(401, "unauthenticated", "Authentication required.")

    sessions = SessionService(db, ttl_days=settings.momdiary_session_cookie_ttl_days)
    sess = await sessions.get_active(token)
    if sess is None:
        raise _error(401, "unauthenticated", "Session is invalid or expired.")

    user = (
        await db.execute(select(User).where(User.id == sess.user_id))
    ).scalar_one_or_none()
    if user is None or user.deleted_at is not None:
        raise _error(401, "unauthenticated", "Account is no longer active.")

    await sessions.touch(sess)
    request.state.user_id = user.id
    request.state.session_token = token
    return AuthContext(user=user, session_token=token)


CurrentUserDep = Annotated[AuthContext, Depends(current_user)]


async def require_active_baby(
    request: Request,
    auth: CurrentUserDep,
    db: Annotated[AsyncSession, Depends(get_session)],
    x_active_baby_id: Annotated[str | None, Header()] = None,
) -> Baby:
    """Resolve the current request's active baby (research §R7).

    Precedence:
      1. `X-Active-Baby-Id` header (per-request override).
      2. `users.active_baby_id` (persisted).
    Errors:
      * 409 `no_active_baby` if neither resolves.
      * 404 `not_found` if the requested baby doesn't exist or isn't owned
        by the caller (FR-016: never leak cross-tenant existence).
    """
    user = auth.user
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
    return baby


ActiveBabyDep = Annotated[Baby, Depends(require_active_baby)]
