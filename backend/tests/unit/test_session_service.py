"""Unit tests for SessionService — feature 006 T016."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.auth.sessions import SessionService


@pytest.mark.asyncio
async def test_create_returns_row_with_token_pk(
    session: AsyncSession, seed_caregiver
) -> None:
    svc = SessionService(session, ttl_days=30)
    row = await svc.create(user_id=seed_caregiver.user_id, user_agent="pytest")
    assert isinstance(row.id, str) and len(row.id) > 30
    assert row.user_id == seed_caregiver.user_id
    assert row.revoked_at is None


@pytest.mark.asyncio
async def test_get_active_returns_none_for_unknown_token(
    session: AsyncSession,
) -> None:
    svc = SessionService(session, ttl_days=30)
    assert await svc.get_active("does-not-exist") is None
    assert await svc.get_active("") is None


@pytest.mark.asyncio
async def test_revoke_then_get_active_returns_none(
    session: AsyncSession, seed_caregiver
) -> None:
    svc = SessionService(session, ttl_days=30)
    row = await svc.create(user_id=seed_caregiver.user_id, user_agent=None)
    await svc.revoke(row.id)
    await session.flush()
    assert await svc.get_active(row.id) is None


@pytest.mark.asyncio
async def test_touch_slides_expiry_forward(
    session: AsyncSession, seed_caregiver
) -> None:
    svc = SessionService(session, ttl_days=30)
    row = await svc.create(user_id=seed_caregiver.user_id, user_agent=None)
    # Force a backward-dated expiry so touch's effect is observable.
    backdated = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(
        timespec="seconds"
    )
    row.expires_at = backdated
    await svc.touch(row)
    assert row.expires_at > backdated


@pytest.mark.asyncio
async def test_expired_session_is_not_returned(
    session: AsyncSession, seed_caregiver
) -> None:
    svc = SessionService(session, ttl_days=30)
    row = await svc.create(user_id=seed_caregiver.user_id, user_agent=None)
    # Manually expire.
    row.expires_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(
        timespec="seconds"
    )
    await session.flush()
    assert await svc.get_active(row.id) is None
