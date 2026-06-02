"""Per-request context for the active baby (feature 006) and timezone (007).

We use contextvars rather than threading state through every repository and
agent-tool signature. FastAPI runs each request as a single asyncio task, so
each var propagates across `await`s within that request and is invisible to
other requests.

- `_active_baby_id` is set by `momdiary.auth.dependencies.require_active_baby`
  once the active baby is resolved; consumed by baby-scoped repositories.
- `_active_user_timezone` is set by `current_user` once the caregiver row is
  loaded (feature 007); consumed by the agent's read tools and the MAF
  context formatter, which have no `User` in their natural signatures.
"""

from __future__ import annotations

from contextvars import ContextVar
from zoneinfo import ZoneInfo

_active_baby_id: ContextVar[int | None] = ContextVar(
    "momdiary_active_baby_id", default=None
)

_active_user_timezone: ContextVar[ZoneInfo | None] = ContextVar(
    "momdiary_active_user_timezone", default=None
)


def set_active_baby_id(baby_id: int | None) -> None:
    _active_baby_id.set(baby_id)


def get_active_baby_id() -> int | None:
    return _active_baby_id.get()


def require_active_baby_id() -> int:
    """Use inside repositories that MUST scope to a baby. Raises if unset."""
    value = _active_baby_id.get()
    if value is None:
        raise RuntimeError(
            "current_baby_id is not set — call require_active_baby() in your "
            "route's dependency chain before invoking baby-scoped repositories."
        )
    return value


def set_active_user_timezone(tz: ZoneInfo | None) -> None:
    _active_user_timezone.set(tz)


def get_active_user_timezone() -> ZoneInfo | None:
    """Return the per-request caregiver TZ if set, else None.

    Callers that need a *guaranteed* TZ (agent tools, MAF context) fall back
    to `time_service.get_default_timezone` when this returns None.
    """
    return _active_user_timezone.get()
