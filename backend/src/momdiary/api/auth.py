"""Auth endpoints (feature 006 US1)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.auth.dependencies import CurrentUserDep
from momdiary.auth.hasher import PasswordHasherService, get_password_hasher
from momdiary.auth.sessions import SessionService
from momdiary.config import get_settings
from momdiary.db.engine import get_session
from momdiary.models.orm import User
from momdiary.observability.logging import get_logger
from momdiary.observability.middleware import current_correlation_id
from momdiary.schemas.auth import (
    AuthSessionInfo,
    LoginRequest,
    RegisterRequest,
    UserPublic,
)

logger = get_logger(__name__)

router = APIRouter(tags=["auth"], prefix="/auth")


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={
            "error": code,
            "message": message,
            "correlation_id": current_correlation_id() or "unknown",
        },
    )


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.momdiary_session_cookie_name,
        value=token,
        max_age=settings.momdiary_session_cookie_ttl_days * 86_400,
        httponly=True,
        secure=settings.momdiary_session_cookie_secure,
        samesite=settings.momdiary_session_cookie_samesite,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.momdiary_session_cookie_name,
        path="/",
    )


def _public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        active_baby_id=user.active_baby_id,
    )


@router.post("/register", response_model=AuthSessionInfo, status_code=201)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_session)],
    hasher: Annotated[PasswordHasherService, Depends(get_password_hasher)],
) -> AuthSessionInfo:
    """Create a new caregiver account and issue a session cookie."""
    settings = get_settings()
    # Pre-check for duplicate (case-insensitive). Done as a query rather than
    # relying on the UNIQUE index so we can return a uniform error envelope.
    existing = (
        await db.execute(
            select(User.id).where(User.email.collate("NOCASE") == payload.email)
        )
    ).first()
    if existing is not None:
        # FR-006 wants uniform 401 for invalid credentials, but registration
        # collision is its own case → 409 conflict (per contract). Still run
        # a dummy verify to keep hashing time consistent across paths.
        hasher.dummy_verify()
        raise _error(
            409, "conflict", "An account with that email already exists."
        )

    user = User(
        email=payload.email,
        password_hash=hasher.hash(payload.password),
        display_name=payload.display_name,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as err:
        # Race: another concurrent registration won.
        await db.rollback()
        raise _error(409, "conflict", "An account with that email already exists.") from err

    sessions = SessionService(db, ttl_days=settings.momdiary_session_cookie_ttl_days)
    sess = await sessions.create(
        user_id=user.id, user_agent=request.headers.get("user-agent")
    )
    await db.commit()
    _set_session_cookie(response, sess.id)
    logger.info("auth.register", user_id=user.id)
    return AuthSessionInfo(user=_public(user))


@router.post("/login", response_model=AuthSessionInfo)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_session)],
    hasher: Annotated[PasswordHasherService, Depends(get_password_hasher)],
) -> AuthSessionInfo:
    """Verify credentials and issue a session cookie."""
    settings = get_settings()
    user = (
        await db.execute(
            select(User).where(
                User.email.collate("NOCASE") == payload.email,
                User.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if user is None:
        # Constant-time dummy verify so the response time doesn't leak
        # whether the email exists (research §R8).
        hasher.dummy_verify()
        raise _error(401, "invalid_credentials", "Invalid email or password.")

    if not hasher.verify(user.password_hash, payload.password):
        raise _error(401, "invalid_credentials", "Invalid email or password.")

    # Opportunistic rehash if the cost parameters have been raised.
    if hasher.needs_rehash(user.password_hash):
        user.password_hash = hasher.hash(payload.password)
        await db.flush()

    sessions = SessionService(db, ttl_days=settings.momdiary_session_cookie_ttl_days)
    sess = await sessions.create(
        user_id=user.id, user_agent=request.headers.get("user-agent")
    )
    await db.commit()
    _set_session_cookie(response, sess.id)
    logger.info("auth.login", user_id=user.id)
    return AuthSessionInfo(user=_public(user))


@router.post("/logout")
async def logout(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_session)],
    auth: CurrentUserDep,
) -> dict[str, bool]:
    settings = get_settings()
    sessions = SessionService(db, ttl_days=settings.momdiary_session_cookie_ttl_days)
    await sessions.revoke(auth.session_token)
    await db.commit()
    _clear_session_cookie(response)
    logger.info("auth.logout", user_id=auth.user.id)
    return {"ok": True}


@router.get("/me", response_model=AuthSessionInfo)
async def me(auth: CurrentUserDep) -> AuthSessionInfo:
    return AuthSessionInfo(user=_public(auth.user))
