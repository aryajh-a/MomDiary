"""Time-zone aware helpers (FR-009, FR-012)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.config import get_settings
from momdiary.models.orm import SettingsRow, User
from momdiary.observability.logging import get_logger

logger = get_logger(__name__)

_cached_tz: ZoneInfo | None = None


async def get_default_timezone(session: AsyncSession) -> ZoneInfo:
    """Read the default timezone from the singleton settings row.

    Falls back to env-var configured zone if the settings row is absent
    (e.g., very early in startup).
    """
    global _cached_tz
    if _cached_tz is not None:
        return _cached_tz
    row = (
        await session.execute(select(SettingsRow).where(SettingsRow.id == 1))
    ).scalar_one_or_none()
    tz_name = row.default_timezone if row else get_settings().momdiary_default_timezone
    _cached_tz = ZoneInfo(tz_name)
    return _cached_tz


async def get_user_timezone(session: AsyncSession, user: User) -> ZoneInfo:
    """Return the caregiver's IANA timezone (feature 007).

    If the user has no stored TZ (legacy null, or a buggy client never sent
    one) we fall back to the system default. An invalid IANA string is also
    treated as "no preference" and logged so the bad value can be diagnosed
    after the fact.
    """
    if user.timezone:
        try:
            return ZoneInfo(user.timezone)
        except ZoneInfoNotFoundError:
            logger.warning(
                "user.timezone.invalid",
                user_id=user.id,
                value=user.timezone,
            )
    return await get_default_timezone(session)


def reset_timezone_cache() -> None:
    """Test-only helper."""
    global _cached_tz
    _cached_tz = None


def now_in_tz(tz: ZoneInfo) -> datetime:
    return datetime.now(tz)


def parse_iso_with_offset(value: str) -> datetime:
    """Parse an ISO-8601 string. Naive strings are rejected (FR-012)."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include an offset: {value!r}")
    return parsed


def to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("Refusing to serialize a naive datetime.")
    return value.isoformat(timespec="seconds")


def date_window_in_tz(d: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Return [start, end) of the local calendar date `d` in zone `tz`."""
    start_local = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local, end_local
