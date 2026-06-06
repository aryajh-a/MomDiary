"""Unit tests for `pg_session_store._turn_to_json` / `_turn_from_json`.

These cover the JSONB serialization contract documented in
`specs/011-research-web-context/contracts/session-store.md`.

The full round-trip through Postgres is exercised by the integration suite
under `backend/tests/integration/`; here we only assert the per-turn
serializer / deserializer pair, which is the surface that defines the
on-wire shape of a row in `chat_sessions.turns`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from momdiary.agents.pg_session_store import _turn_from_json, _turn_to_json
from momdiary.agents.session_store import ChatTurn


def _make_turn(**overrides: object) -> ChatTurn:
    base = {
        "role": "assistant",
        "text": "Most pediatric guidance suggests 10–12 hours overnight ...",
        "correlation_id": "00000000-0000-4000-8000-000000000001",
        "created_at": datetime(2026, 6, 5, 10, 0, 0, tzinfo=UTC),
        "outcome": "research_answer",
    }
    base.update(overrides)
    return ChatTurn(**base)  # type: ignore[arg-type]


def test_roundtrip_research_turn_with_sources() -> None:
    """A research turn with citations round-trips losslessly through the JSONB pair."""
    sources = [
        {
            "title": "Sleep — HealthyChildren.org (AAP)",
            "url": "https://www.healthychildren.org/English/ages-stages/baby/sleep/",
        },
        {
            "title": "Baby sleep patterns — NHS",
            "url": "https://www.nhs.uk/conditions/baby/caring-for-a-newborn/helping-your-baby-to-sleep/",
        },
    ]
    turn = _make_turn(sources=sources)

    serialized = _turn_to_json(turn)
    assert serialized["sources"] == sources
    # `asdict` flattens nested dicts and emits ISO datetimes.
    assert serialized["created_at"] == "2026-06-05T10:00:00+00:00"

    restored = _turn_from_json(serialized)
    assert restored == turn
    assert restored.sources == sources


def test_roundtrip_diary_turn_keeps_sources_as_none() -> None:
    """A diary turn (no `sources` set) round-trips with `sources is None`."""
    turn = _make_turn(
        role="caregiver",
        text="logged a feed",
        outcome=None,
        entry_type=None,
        entry_id=None,
    )
    # No sources passed → default None.
    assert turn.sources is None

    serialized = _turn_to_json(turn)
    # `asdict` always emits the key (None) — both shapes (`None` or
    # missing) are accepted on read; see test_backcompat below.
    assert serialized.get("sources", None) is None

    restored = _turn_from_json(serialized)
    assert restored.sources is None
    assert restored == turn


def test_roundtrip_empty_sources_list_preserved() -> None:
    """An empty sources list (refused / no-source-found turn) round-trips as `[]`."""
    turn = _make_turn(outcome="no_sources_found", sources=[])

    serialized = _turn_to_json(turn)
    assert serialized["sources"] == []

    restored = _turn_from_json(serialized)
    assert restored.sources == []
    # `[] is not None` — the runner relies on this distinction (FR-013).
    assert restored.sources is not None


@pytest.mark.parametrize(
    "outcome",
    [
        "research_answer",
        "research_unavailable",
        "scope_refused",
        "safety_refused",
        "no_sources_found",
    ],
)
def test_research_outcome_literal_accepted(outcome: str) -> None:
    """Each research outcome string is accepted by ChatTurn and round-trips."""
    turn = _make_turn(outcome=outcome, sources=[])
    serialized = _turn_to_json(turn)
    assert serialized["outcome"] == outcome
    restored = _turn_from_json(serialized)
    assert restored.outcome == outcome
