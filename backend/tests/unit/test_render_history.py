"""T014: unit tests for `_render_history` (FR-004)."""

from __future__ import annotations

from datetime import datetime, timezone

from momdiary.agents.maf_runner import _render_history
from momdiary.agents.session_store import ChatTurn


def _now() -> datetime:
    return datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)


def test_empty_history_renders_to_empty_string() -> None:
    assert _render_history([]) == ""


def test_caregiver_only_turn() -> None:
    turn = ChatTurn(
        role="caregiver",
        text="120 ml breast milk just now",
        correlation_id="cid-1",
        created_at=_now(),
    )
    assert _render_history([turn]) == "Caregiver: 120 ml breast milk just now"


def test_assistant_write_turn_has_parenthetical() -> None:
    history = [
        ChatTurn(
            role="caregiver",
            text="120 ml breast milk just now",
            correlation_id="cid-1",
            created_at=_now(),
        ),
        ChatTurn(
            role="assistant",
            text="Logged feed.",
            correlation_id="cid-1",
            created_at=_now(),
            outcome="created",
            entry_type="feed",
            entry_id=42,
        ),
    ]
    rendered = _render_history(history)
    assert rendered == (
        "Caregiver: 120 ml breast milk just now\n"
        "Assistant: Logged feed. (created feed#42)"
    )


def test_assistant_clarification_turn_has_no_parenthetical() -> None:
    history = [
        ChatTurn(
            role="caregiver",
            text="baby ate",
            correlation_id="cid-1",
            created_at=_now(),
        ),
        ChatTurn(
            role="assistant",
            text="What time did the feed happen?",
            correlation_id="cid-1",
            created_at=_now(),
            outcome="clarification_requested",
        ),
    ]
    rendered = _render_history(history)
    assert rendered == (
        "Caregiver: baby ate\n"
        "Assistant: What time did the feed happen?"
    )
    assert "(" not in rendered


def test_ordering_is_oldest_to_newest() -> None:
    t1 = ChatTurn(role="caregiver", text="first", correlation_id="a", created_at=_now())
    t2 = ChatTurn(role="assistant", text="second", correlation_id="a", created_at=_now())
    t3 = ChatTurn(role="caregiver", text="third", correlation_id="b", created_at=_now())
    rendered = _render_history([t1, t2, t3])
    lines = rendered.split("\n")
    assert lines == [
        "Caregiver: first",
        "Assistant: second",
        "Caregiver: third",
    ]


def test_assistant_updated_outcome_with_entry_metadata() -> None:
    turn = ChatTurn(
        role="assistant",
        text="Updated feed.",
        correlation_id="cid",
        created_at=_now(),
        outcome="updated",
        entry_type="feed",
        entry_id=7,
    )
    assert _render_history([turn]) == "Assistant: Updated feed. (updated feed#7)"
