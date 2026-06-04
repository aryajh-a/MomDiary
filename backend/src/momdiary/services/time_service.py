"""Time-zone aware helpers (FR-009, FR-012)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.config import get_settings
from momdiary.models.orm import SettingsRow
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


def reset_timezone_cache() -> None:
    """Test-only helper."""
    global _cached_tz
    _cached_tz = None


def parse_zoneinfo_or_none(name: str | None) -> ZoneInfo | None:
    """Return a ZoneInfo for a valid IANA name, else None (feature 009).

    Used both to set the per-request timezone contextvar (from the stored
    `users.timezone`) and to validate the `timezone` field on
    `PATCH /v1/users/me`. Invalid/unknown names are ignored (logged, returns
    None) so a buggy client can never break the request (FR-002).
    """
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("user.timezone.invalid", value=name)
        return None


async def get_request_timezone(session: AsyncSession) -> ZoneInfo:
    """Resolve the timezone for the current request (feature 009).

    Prefers the authenticated caregiver's zone (set on a contextvar by
    `auth.dependencies.get_current_user`); falls back to the system default
    when unset. This is the single resolver every consumer calls — repos,
    the agent's read tools, and the agent's `Current local time:` prefix.
    """
    # Imported lazily to avoid a module import cycle (auth.context is a leaf,
    # but auth.dependencies imports this module).
    from momdiary.auth.context import get_active_user_timezone

    return get_active_user_timezone() or await get_default_timezone(session)


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


def to_utc_iso(value: str) -> str:
    """Normalize an aware ISO-8601 string to its UTC (`+00:00`) representation.

    Every persisted timestamp passes through here so stored rows share one
    offset. The date-window filter in `date_window_in_tz` compares timestamps
    as strings, and lexicographic order only matches chronological order when
    all operands share an offset — so a row written with a non-UTC offset
    (e.g. a future native mobile client sending `+05:30`) would mis-bucket near
    the date boundary. Normalizing on write makes correct bucketing independent
    of the client. Naive inputs are rejected by `parse_iso_with_offset` (FR-012).
    """
    return to_iso(parse_iso_with_offset(value).astimezone(timezone.utc))


def date_window_in_tz(d: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Return [start, end) of local calendar date `d` in zone `tz`, as UTC.

    The bounds are normalized to UTC so that when callers serialize them with
    `to_iso(...)` and compare against the UTC-stored `occurred_at`/`start_at`
    strings, the comparison is chronological. ISO-8601 string comparison only
    matches chronological order when both operands share one offset; emitting
    the bounds in the window's local offset (e.g. +05:30) while rows are stored
    in +00:00 silently mis-buckets entries near the date boundary (feature 009).
    """
    start_local = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
