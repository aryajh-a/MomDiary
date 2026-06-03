"""Unit tests for time_service helpers (T070)."""

from __future__ import annotations

from datetime import date

import pytest
from zoneinfo import ZoneInfo

from momdiary.services.time_service import (
    date_window_in_tz,
    parse_iso_with_offset,
    to_iso,
    to_utc_iso,
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


def test_to_utc_iso_normalizes_offset() -> None:
    # A non-UTC offset (e.g. a native mobile client) collapses to the same
    # instant expressed in UTC, so persisted rows share one offset and the
    # date-window string comparison buckets them correctly.
    assert to_utc_iso("2026-06-03T02:50:00+05:30") == "2026-06-02T21:20:00+00:00"


def test_to_utc_iso_passes_through_utc() -> None:
    assert to_utc_iso("2026-06-02T21:20:00+00:00") == "2026-06-02T21:20:00+00:00"
    assert to_utc_iso("2026-06-02T21:20:00Z") == "2026-06-02T21:20:00+00:00"


def test_to_utc_iso_rejects_naive() -> None:
    with pytest.raises(ValueError):
        to_utc_iso("2026-06-02T21:20:00")


def test_date_window_basic() -> None:
    tz = ZoneInfo("America/Los_Angeles")
    start, end = date_window_in_tz(date(2026, 5, 16), tz)
    # Feature 009: bounds are normalized to UTC so string comparison against the
    # UTC-stored timestamps stays chronological. Midnight PDT (-07:00) == 07:00Z.
    assert start.isoformat() == "2026-05-16T07:00:00+00:00"
    assert end.isoformat() == "2026-05-17T07:00:00+00:00"


def test_date_window_dst_spring_forward() -> None:
    """DST starts 2026-03-08 in Los_Angeles."""
    tz = ZoneInfo("America/Los_Angeles")
    start, end = date_window_in_tz(date(2026, 3, 8), tz)
    assert (end - start).total_seconds() == 23 * 3600
