"""Per-request context for the active baby (feature 006).

We use a contextvar rather than threading `baby_id` through every repository
and agent-tool signature. FastAPI runs each request as a single asyncio task,
so the var propagates across `await`s within that request and is invisible
to other requests.

Set by `momdiary.auth.dependencies.require_active_baby` once it's resolved
the active baby; consumed by repositories on insert/select and by the
agent-interactions logger to satisfy the new `baby_id NOT NULL` FK
(feature 006 FR-014 / FR-018).
"""

from __future__ import annotations

from contextvars import ContextVar
from zoneinfo import ZoneInfo

_active_baby_id: ContextVar[int | None] = ContextVar(
    "momdiary_active_baby_id", default=None
)

# Feature 009 — per-request caregiver timezone. Set by
# `auth.dependencies.get_current_user` (runs on every authenticated request),
# read by `services.time_service.get_request_timezone` so repositories and the
# agent resolve date windows in the caregiver's zone without threading it
# through every signature. None ⇒ consumers fall back to the system default.
_active_user_timezone: ContextVar[ZoneInfo | None] = ContextVar(
    "momdiary_active_user_timezone", default=None
)


def set_active_baby_id(baby_id: int | None) -> None:
    _active_baby_id.set(baby_id)


def get_active_baby_id() -> int | None:
    return _active_baby_id.get()


def set_active_user_timezone(tz: ZoneInfo | None) -> None:
    _active_user_timezone.set(tz)


def get_active_user_timezone() -> ZoneInfo | None:
    return _active_user_timezone.get()


def require_active_baby_id() -> int:
    """Use inside repositories that MUST scope to a baby. Raises if unset."""
    value = _active_baby_id.get()
    if value is None:
        raise RuntimeError(
            "current_baby_id is not set — call require_active_baby() in your "
            "route's dependency chain before invoking baby-scoped repositories."
        )
    return value
