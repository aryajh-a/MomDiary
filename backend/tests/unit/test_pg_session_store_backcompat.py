"""Backward-compatibility tests for `pg_session_store._turn_from_json`.

JSONB rows written before feature 011 have no `sources` key. This module
proves they continue to deserialize cleanly, with `ChatTurn.sources = None`.

Contract: `specs/011-research-web-context/contracts/session-store.md` §3
"Default on read".
"""

from __future__ import annotations

from datetime import UTC, datetime

from momdiary.agents.pg_session_store import _turn_from_json
from momdiary.agents.session_store import ChatTurn


_BASE_TIMESTAMP = "2026-05-01T08:00:00+00:00"


def test_legacy_caregiver_turn_without_sources_key_loads() -> None:
    """A pre-011 caregiver row (no `sources` key) deserializes with sources=None."""
    legacy_row = {
        "role": "caregiver",
        "text": "I fed her 120 ml at 8am",
        "correlation_id": "11111111-1111-4111-8111-111111111111",
        "created_at": _BASE_TIMESTAMP,
        # outcome / entry_type / entry_id absent as on real pre-feature rows.
    }
    turn = _turn_from_json(legacy_row)

    assert isinstance(turn, ChatTurn)
    assert turn.role == "caregiver"
    assert turn.text == "I fed her 120 ml at 8am"
    assert turn.correlation_id == "11111111-1111-4111-8111-111111111111"
    assert turn.created_at == datetime(2026, 5, 1, 8, 0, 0, tzinfo=UTC)
    assert turn.outcome is None
    assert turn.entry_type is None
    assert turn.entry_id is None
    # Key invariant: the absent `sources` key reads as `None`, not as an
    # empty list (which would imply a research turn that found no sources).
    assert turn.sources is None


def test_legacy_diary_assistant_turn_without_sources_key_loads() -> None:
    """A pre-011 assistant diary row (with outcome, no `sources` key) deserializes cleanly."""
    legacy_row = {
        "role": "assistant",
        "text": "Logged a 120 ml formula feed at 8:00 AM.",
        "correlation_id": "22222222-2222-4222-8222-222222222222",
        "created_at": _BASE_TIMESTAMP,
        "outcome": "created",
        "entry_type": "feed",
        "entry_id": 42,
    }
    turn = _turn_from_json(legacy_row)

    assert turn.role == "assistant"
    assert turn.outcome == "created"
    assert turn.entry_type == "feed"
    assert turn.entry_id == 42
    assert turn.sources is None


def test_explicit_null_sources_key_loads_as_none() -> None:
    """A row that writes `sources: null` explicitly also deserializes as `None`."""
    row = {
        "role": "caregiver",
        "text": "hi",
        "correlation_id": "33333333-3333-4333-8333-333333333333",
        "created_at": _BASE_TIMESTAMP,
        "sources": None,
    }
    turn = _turn_from_json(row)
    assert turn.sources is None


def test_new_research_turn_with_sources_loads_back_into_list() -> None:
    """Feature 011 row (sources populated) deserializes into a list of dicts."""
    row = {
        "role": "assistant",
        "text": "Pediatric guidance ... not medical advice.",
        "correlation_id": "44444444-4444-4444-8444-444444444444",
        "created_at": _BASE_TIMESTAMP,
        "outcome": "research_answer",
        "sources": [
            {"title": "AAP", "url": "https://www.healthychildren.org/x"},
            {"title": "NHS", "url": "https://www.nhs.uk/y"},
        ],
    }
    turn = _turn_from_json(row)
    assert turn.outcome == "research_answer"
    assert turn.sources is not None
    assert len(turn.sources) == 2
    assert turn.sources[0] == {"title": "AAP", "url": "https://www.healthychildren.org/x"}
