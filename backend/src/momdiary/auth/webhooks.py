"""Clerk webhook handler — feature 008.

Verifies Svix signatures, then dispatches `user.deleted` (cascade hard-
delete of the caregiver + every owned baby + every diary row + chat-store
purge) and `user.updated` (mirror email + email_verified state).

Per `specs/008-clerk-auth/data-model.md` §4, the deletion cascade runs in
one SQLAlchemy transaction in FK-safe order:
    appointment_notes -> appointments -> poops -> sleeps -> feeds
    -> agent_interactions -> babies -> users
Replays are idempotent (DELETE on already-empty data is a no-op).
"""

from __future__ import annotations

import structlog
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError

from momdiary.config import get_settings
from momdiary.models.orm import (
    AgentInteraction,
    Appointment,
    AppointmentNote,
    Baby,
    Feed,
    Poop,
    Sleep,
    User,
)

logger = structlog.get_logger(__name__)


class WebhookSignatureError(Exception):
    """Raised when the Svix signature check fails."""


def verify_svix(headers: dict[str, str], body: bytes) -> None:
    """Verify a Svix-signed webhook body. Raises `WebhookSignatureError`."""
    settings = get_settings()
    secret = settings.clerk_webhook_secret
    if not secret:
        raise WebhookSignatureError("CLERK_WEBHOOK_SECRET is not configured.")
    try:
        wh = Webhook(secret)
        wh.verify(body, headers)
    except WebhookVerificationError as err:
        raise WebhookSignatureError(str(err)) from err


async def handle_user_deleted(
    db: AsyncSession,
    *,
    clerk_user_id: str,
    chat_store_purge,  # noqa: ANN001 — Callable[[int], Awaitable[int]]
) -> int:
    """Cascade-delete every row owned by `clerk_user_id`.

    Returns the number of caregiver rows deleted (0 = no-op replay).
    """
    user = (
        await db.execute(select(User).where(User.clerk_user_id == clerk_user_id))
    ).scalar_one_or_none()
    if user is None:
        logger.info("webhook.user_deleted.noop", clerk_user_id=clerk_user_id)
        return 0

    user_id = user.id
    baby_ids = list(
        (
            await db.execute(select(Baby.id).where(Baby.owner_user_id == user_id))
        ).scalars()
    )

    if baby_ids:
        # Children first, then parents.
        # AppointmentNote → Appointment is FK-cascade via ORM relationship,
        # but we issue explicit DELETEs to be transactionally explicit and
        # to keep ordering deterministic regardless of cascade configuration.
        appt_ids = list(
            (
                await db.execute(
                    select(Appointment.id).where(Appointment.baby_id.in_(baby_ids))
                )
            ).scalars()
        )
        if appt_ids:
            await db.execute(
                delete(AppointmentNote).where(
                    AppointmentNote.appointment_id.in_(appt_ids)
                )
            )
        await db.execute(delete(Appointment).where(Appointment.baby_id.in_(baby_ids)))
        await db.execute(delete(Poop).where(Poop.baby_id.in_(baby_ids)))
        await db.execute(delete(Sleep).where(Sleep.baby_id.in_(baby_ids)))
        await db.execute(delete(Feed).where(Feed.baby_id.in_(baby_ids)))
        await db.execute(
            delete(AgentInteraction).where(AgentInteraction.baby_id.in_(baby_ids))
        )
        # Detach active_baby_id before deleting baby rows to satisfy the
        # users.active_baby_id FK on SQLite (use_alter=True at ORM level).
        await db.execute(
            text("UPDATE users SET active_baby_id = NULL WHERE id = :uid"),
            {"uid": user_id},
        )
        await db.execute(delete(Baby).where(Baby.owner_user_id == user_id))

    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()

    purged = await chat_store_purge(user_id)
    logger.info(
        "webhook.user_deleted.cascade",
        clerk_user_id=clerk_user_id,
        user_id=user_id,
        babies=len(baby_ids),
        chat_sessions_purged=purged,
    )
    return 1


async def handle_user_updated(
    db: AsyncSession,
    *,
    clerk_user_id: str,
    email: str | None,
    email_verified: bool | None,
) -> bool:
    """Mirror email + verification state from a `user.updated` event."""
    user = (
        await db.execute(select(User).where(User.clerk_user_id == clerk_user_id))
    ).scalar_one_or_none()
    if user is None:
        # Lazy-provision happens on the next API call; nothing to do here.
        logger.info("webhook.user_updated.noop", clerk_user_id=clerk_user_id)
        return False

    from datetime import datetime, timezone

    def _utcnow_iso() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    mutated = False
    if email and user.email != email:
        user.email = email
        mutated = True
    if email_verified is True and user.email_verified_at is None:
        user.email_verified_at = _utcnow_iso()
        mutated = True
    elif email_verified is False and user.email_verified_at is not None:
        user.email_verified_at = None
        mutated = True
    if mutated:
        user.updated_at = _utcnow_iso()
        await db.commit()
    return mutated


__all__ = [
    "WebhookSignatureError",
    "handle_user_deleted",
    "handle_user_updated",
    "verify_svix",
]
