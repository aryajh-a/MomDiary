"""Contract tests: argument schemas for log_* tools (T022)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from momdiary.agents.tools.appointments import LogAppointmentArgs
from momdiary.agents.tools.feeds import LogFeedArgs
from momdiary.agents.tools.poops import LogPoopArgs
from momdiary.agents.tools.sleeps import LogSleepArgs


def test_log_feed_args_accepts_canonical_payload() -> None:
    args = LogFeedArgs(
        feed_type="breast_milk",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )
    assert args.feed_type == "breast_milk"
    assert args.quantity == 120


def test_log_feed_rejects_invalid_feed_type() -> None:
    with pytest.raises(ValidationError):
        LogFeedArgs(
            feed_type="juice",  # type: ignore[arg-type]
            quantity=120,
            unit="ml",
            occurred_at="2026-05-16T08:00:00-07:00",
        )


def test_log_feed_rejects_non_positive_quantity() -> None:
    with pytest.raises(ValidationError):
        LogFeedArgs(
            feed_type="formula",
            quantity=0,
            unit="ml",
            occurred_at="2026-05-16T08:00:00-07:00",
        )


def test_log_sleep_args_round_trip() -> None:
    args = LogSleepArgs(
        start_at="2026-05-16T13:00:00-07:00",
        end_at="2026-05-16T14:30:00-07:00",
    )
    assert args.start_at != args.end_at


def test_log_poop_args_enforces_consistency_enum() -> None:
    LogPoopArgs(occurred_at="2026-05-16T10:00:00-07:00", consistency="soft")
    with pytest.raises(ValidationError):
        LogPoopArgs(
            occurred_at="2026-05-16T10:00:00-07:00",
            consistency="goopy",  # type: ignore[arg-type]
        )


def test_log_appointment_accepts_optional_note() -> None:
    args = LogAppointmentArgs(
        scheduled_at="2026-05-20T09:00:00-07:00", note="Bring vaccine record"
    )
    assert args.note == "Bring vaccine record"
    bare = LogAppointmentArgs(scheduled_at="2026-05-20T09:00:00-07:00")
    assert bare.note is None
