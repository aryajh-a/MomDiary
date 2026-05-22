"""Opaque-token rolling session service — feature 006 (research §R2)."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.models.orm import UserSession


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _parse(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


class SessionService:
    """CRUD for `user_sessions` rows.

    Session ids are 32-byte `secrets.token_urlsafe` strings (≈ 43 chars,
    ≥ 256 bits of entropy). They are stored as the table PK and returned
    verbatim as the cookie value.
    """

    def __init__(self, db: AsyncSession, *, ttl_days: int = 30) -> None:
        self._db = db
        self._ttl = timedelta(days=ttl_days)

    async def create(
        self, *, user_id: int, user_agent: str | None
    ) -> UserSession:
        token = secrets.token_urlsafe(32)
        now = _utcnow()
        row = UserSession(
            id=token,
            user_id=user_id,
            created_at=_iso(now),
            expires_at=_iso(now + self._ttl),
            last_seen_at=_iso(now),
            revoked_at=None,
            user_agent=(user_agent[:512] if user_agent else None),
        )
        self._db.add(row)
        await self._db.flush()
        return row

    async def get_active(self, token: str) -> UserSession | None:
        """Return the session iff it exists, is not revoked, and not expired."""
        if not token:
            return None
        stmt = select(UserSession).where(UserSession.id == token)
        row = (await self._db.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        if row.revoked_at is not None:
            return None
        if _parse(row.expires_at) <= _utcnow():
            return None
        return row

    async def touch(self, session: UserSession) -> None:
        """Slide `expires_at` forward by TTL and bump `last_seen_at`."""
        now = _utcnow()
        new_expires = now + self._ttl
        session.last_seen_at = _iso(now)
        session.expires_at = _iso(new_expires)
        await self._db.flush()

    async def revoke(self, token: str) -> None:
        """Idempotent — sets revoked_at if the row exists and is not already revoked."""
        now_iso = _iso(_utcnow())
        await self._db.execute(
            update(UserSession)
            .where(UserSession.id == token, UserSession.revoked_at.is_(None))
            .values(revoked_at=now_iso)
        )
