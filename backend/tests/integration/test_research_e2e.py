"""T008 — Integration tests for `ResearchRunner`.

Exercises the runner end-to-end with a stub `WebSearchPort` and the
process-local `InMemorySessionStore`. Asserts the runner:

* persists both the caregiver and assistant turns,
* attaches the clamped `sources` list onto the assistant turn,
* records `outcome="research_answer"` on success,
* falls back to `outcome="research_unavailable"` with `sources=[]` on
  timeout / upstream error and still appends the failure turn (FR-022).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from momdiary.agents.research_runner import ResearchRunner
from momdiary.agents.session_store import InMemorySessionStore


class _StubWebSearch:
    """Test double for `WebSearchPort`.

    Configure either `result` (the (synthesized_text, citations) tuple it
    returns) or `raise_exc` (the exception to raise). Optionally honors
    `delay_seconds` so timeout tests can stall the call.
    """

    def __init__(
        self,
        *,
        result: tuple[str, list[dict[str, str]]] | None = None,
        raise_exc: BaseException | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self._result = result
        self._raise = raise_exc
        self._delay = delay_seconds
        self.calls: list[tuple[str, str, int]] = []

    async def search(
        self,
        query: str,
        *,
        age_label: str = "",
        history: list[Any] | None = None,
    ) -> tuple[str, list[dict[str, str]]]:
        self.calls.append((query, age_label, len(history or [])))
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        if self._raise is not None:
            raise self._raise
        assert self._result is not None
        return self._result


@pytest.fixture
def store() -> InMemorySessionStore:
    return InMemorySessionStore(
        ttl_seconds=3600,
        max_turns=10,
        max_sessions=100,
        message_max_bytes=4096,
    )


def _runner(
    store: InMemorySessionStore,
    *,
    web_search: Any,
    timeout_seconds: int = 15,
    min_sources: int = 3,
    max_sources: int = 5,
) -> ResearchRunner:
    return ResearchRunner(
        web_search=web_search,
        session_store=store,
        timeout_seconds=timeout_seconds,
        min_sources=min_sources,
        max_sources=max_sources,
    )


# ---------------------------------------------------------------------------
# Happy path: sources persisted on the assistant turn
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runner_persists_sources_on_assistant_turn(
    store: InMemorySessionStore,
) -> None:
    citations = [
        {"title": "AAP", "url": "https://www.healthychildren.org/sleep"},
        {"title": "NHS", "url": "https://www.nhs.uk/sleep"},
        {"title": "CDC", "url": "https://www.cdc.gov/sleep"},
        {"title": "ClevelandClinic", "url": "https://my.clevelandclinic.org/sleep"},
    ]
    web = _StubWebSearch(result=("Pediatric guidance suggests ...", citations))
    runner = _runner(store, web_search=web)

    result = await runner.run(
        "How much sleep does a 4-month-old need?",
        user_id=1,
        baby_id=2,
        baby_age_phrase="4-month-old",
        session_id=None,
        correlation_id="cid-1",
    )

    assert result.outcome == "research_answer"
    assert len(result.sources) == 4  # all 4 fit under max_sources=5
    assert result.session_id  # freshly minted

    # Inspect the session store: both turns persisted, assistant turn
    # carries the sources list.
    session = await store.get_or_create(
        result.session_id, user_id=1, baby_id=2
    )
    turns = list(session.turns)
    assert len(turns) == 2
    assert turns[0].role == "caregiver"
    assert turns[0].sources is None  # caregiver turns never carry sources
    assert turns[1].role == "assistant"
    assert turns[1].outcome == "research_answer"
    assert turns[1].sources == result.sources
    assert turns[1].sources is not None


# ---------------------------------------------------------------------------
# Source clamping: more than max → trimmed to max
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runner_clamps_oversized_source_list_to_max(
    store: InMemorySessionStore,
) -> None:
    citations = [
        {"title": f"src{i}", "url": f"https://example.com/p{i}"} for i in range(8)
    ]
    web = _StubWebSearch(result=("answer", citations))
    runner = _runner(store, web_search=web, max_sources=5)

    result = await runner.run(
        "anything",
        user_id=1,
        baby_id=2,
        baby_age_phrase="",
        session_id=None,
        correlation_id="cid-clamp",
    )

    assert result.outcome == "research_answer"
    assert len(result.sources) == 5  # clamped


# ---------------------------------------------------------------------------
# Zero sources → no_sources_found, FR-013
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runner_returns_no_sources_found_when_search_yields_zero(
    store: InMemorySessionStore,
) -> None:
    web = _StubWebSearch(result=("answer", []))
    runner = _runner(store, web_search=web)

    result = await runner.run(
        "obscure query",
        user_id=1,
        baby_id=2,
        baby_age_phrase="",
        session_id=None,
        correlation_id="cid-zero",
    )

    assert result.outcome == "no_sources_found"
    assert result.sources == []

    # Both turns still persisted (FR-022 — refusals are part of the
    # transcript).
    session = await store.get_or_create(
        result.session_id, user_id=1, baby_id=2
    )
    turns = list(session.turns)
    assert len(turns) == 2
    assert turns[1].outcome == "no_sources_found"
    assert turns[1].sources == []


# ---------------------------------------------------------------------------
# Timeout → research_unavailable, FR-014 + FR-022
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runner_times_out_into_research_unavailable(
    store: InMemorySessionStore,
) -> None:
    # Use a generous configured timeout but make the stub sleep longer.
    web = _StubWebSearch(
        result=("never reached", [{"title": "x", "url": "https://x.com"}]),
        delay_seconds=0.5,
    )
    runner = _runner(store, web_search=web, timeout_seconds=0)
    # `timeout_seconds=0` means immediate timeout; combined with a tiny
    # delay it forces wait_for to raise.

    result = await runner.run(
        "anything",
        user_id=1,
        baby_id=2,
        baby_age_phrase="",
        session_id=None,
        correlation_id="cid-timeout",
    )

    assert result.outcome == "research_unavailable"
    assert result.sources == []

    # Failure turn still persisted.
    session = await store.get_or_create(
        result.session_id, user_id=1, baby_id=2
    )
    turns = list(session.turns)
    assert len(turns) == 2
    assert turns[1].outcome == "research_unavailable"
    assert turns[1].sources == []


# ---------------------------------------------------------------------------
# Upstream exception → research_unavailable, never raises out of the runner
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runner_wraps_upstream_exception_as_research_unavailable(
    store: InMemorySessionStore,
) -> None:
    web = _StubWebSearch(raise_exc=RuntimeError("bing exploded"))
    runner = _runner(store, web_search=web, timeout_seconds=5)

    result = await runner.run(
        "anything",
        user_id=1,
        baby_id=2,
        baby_age_phrase="",
        session_id=None,
        correlation_id="cid-err",
    )

    assert result.outcome == "research_unavailable"
    assert result.sources == []


# ---------------------------------------------------------------------------
# Session continuity: passing an existing session_id reuses it
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runner_reuses_existing_session_when_id_provided(
    store: InMemorySessionStore,
) -> None:
    # First turn (mints a fresh id).
    web = _StubWebSearch(
        result=(
            "first answer",
            [
                {"title": "A", "url": "https://a.com/1"},
                {"title": "B", "url": "https://b.com/2"},
                {"title": "C", "url": "https://c.com/3"},
            ],
        )
    )
    runner = _runner(store, web_search=web)
    first = await runner.run(
        "q1",
        user_id=1,
        baby_id=2,
        baby_age_phrase="",
        session_id=None,
        correlation_id="cid-1",
    )
    second = await runner.run(
        "q2",
        user_id=1,
        baby_id=2,
        baby_age_phrase="",
        session_id=first.session_id,
        correlation_id="cid-2",
    )

    assert second.session_id == first.session_id
    session = await store.get_or_create(
        first.session_id, user_id=1, baby_id=2
    )
    turns = list(session.turns)
    # 2 turns per call × 2 calls = 4 total.
    assert len(turns) == 4
    assert turns[0].text == "q1"
    assert turns[2].text == "q2"
