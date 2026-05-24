"""Shared same-minute dedup helper for `log_*` tools.

Replaces the prompt rule that asked the LLM to call `list_*` before every
`log_*`. Moving this check into the tool layer makes it deterministic,
unit-testable, and impossible to forget.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Iterable, TypeVar

from momdiary.observability.logging import get_logger
from momdiary.services.time_service import parse_iso_with_offset

logger = get_logger(__name__)

T = TypeVar("T")


def _utc_minute(dt: datetime) -> datetime:
    """Truncate to the minute in UTC. Comparison is offset-invariant."""
    return dt.astimezone(timezone.utc).replace(second=0, microsecond=0)


def find_same_minute(
    rows: Iterable[T],
    target_iso: str,
    get_ts: Callable[[T], str],
) -> T | None:
    """Return the first row whose timestamp matches `target_iso` to the
    minute (in absolute UTC), else `None`.

    `rows` is expected to already be scoped to the active baby and to
    exclude soft-deleted entries (this is how `list_by_date` works in
    every repository).
    """
    try:
        target = _utc_minute(parse_iso_with_offset(target_iso))
    except ValueError:
        # Caller's validation will catch malformed timestamps; here we
        # simply degrade to "no dup" so log_* proceeds and the model
        # sees the same validation error path it would have anyway.
        logger.debug("dedup.target_parse_failed", target_iso=target_iso)
        return None

    for row in rows:
        try:
            ts = parse_iso_with_offset(get_ts(row))
        except ValueError:
            continue
        if _utc_minute(ts) == target:
            return row
    return None
