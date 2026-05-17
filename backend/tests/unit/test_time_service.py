"""Unit tests for time_service helpers (T070)."""

from __future__ import annotations

from datetime import date

import pytest
from zoneinfo import ZoneInfo

from momdiary.services.time_service import (
    date_window_in_tz,
    parse_iso_with_offset,
    to_iso,
)


def test_parse_iso_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError):
        parse_iso_with_offset("2026-05-16T08:00:00")


def test_parse_iso_accepts_offset() -> None:
    dt = parse_iso_with_offset("2026-05-16T08:00:00-07:00")
    assert dt.tzinfo is not None
    assert dt.utcoffset() is not None


def test_to_iso_rejects_naive() -> None:
    import datetime as _dt

    with pytest.raises(ValueError):
        to_iso(_dt.datetime(2026, 5, 16, 8, 0, 0))


def test_date_window_basic() -> None:
    tz = ZoneInfo("America/Los_Angeles")
    start, end = date_window_in_tz(date(2026, 5, 16), tz)
    assert start.isoformat() == "2026-05-16T00:00:00-07:00"
    assert end.isoformat() == "2026-05-17T00:00:00-07:00"


def test_date_window_dst_spring_forward() -> None:
    """DST starts 2026-03-08 in Los_Angeles."""
    tz = ZoneInfo("America/Los_Angeles")
    start, end = date_window_in_tz(date(2026, 3, 8), tz)
    assert (end - start).total_seconds() == 23 * 3600
