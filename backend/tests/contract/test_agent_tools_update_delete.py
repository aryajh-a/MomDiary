"""Contract tests for update/delete tool argument schemas (T057)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from momdiary.agents.tools.appointments import (
    AddAppointmentNoteArgs,
    DeleteAppointmentArgs,
    UpdateAppointmentArgs,
)
from momdiary.agents.tools.feeds import DeleteFeedArgs, UpdateFeedArgs
from momdiary.agents.tools.poops import DeletePoopArgs, UpdatePoopArgs
from momdiary.agents.tools.sleeps import DeleteSleepArgs, UpdateSleepArgs


def test_update_feed_args_partial_payload() -> None:
    UpdateFeedArgs(entry_id=1)
    UpdateFeedArgs(entry_id=1, quantity=150)
    with pytest.raises(ValidationError):
        UpdateFeedArgs(entry_id=1, quantity=-1)


def test_delete_feed_args_require_entry_id() -> None:
    with pytest.raises(ValidationError):
        DeleteFeedArgs()  # type: ignore[call-arg]


def test_update_sleep_args_partial_payload() -> None:
    UpdateSleepArgs(entry_id=1, start_at="2026-05-16T13:00:00-07:00")


def test_delete_sleep_args_require_entry_id() -> None:
    DeleteSleepArgs(entry_id=1)


def test_update_poop_args_validate_consistency_enum() -> None:
    UpdatePoopArgs(entry_id=1, consistency="hard")
    with pytest.raises(ValidationError):
        UpdatePoopArgs(entry_id=1, consistency="weird")  # type: ignore[arg-type]


def test_delete_poop_args_require_entry_id() -> None:
    DeletePoopArgs(entry_id=1)


def test_update_appointment_args_partial_payload() -> None:
    UpdateAppointmentArgs(entry_id=1)


def test_delete_appointment_args_require_entry_id() -> None:
    DeleteAppointmentArgs(entry_id=1)


def test_add_appointment_note_args_validate_body_length() -> None:
    AddAppointmentNoteArgs(appointment_id=1, body="ok")
    with pytest.raises(ValidationError):
        AddAppointmentNoteArgs(appointment_id=1, body="")
    with pytest.raises(ValidationError):
        AddAppointmentNoteArgs(appointment_id=1, body="x" * 2001)
