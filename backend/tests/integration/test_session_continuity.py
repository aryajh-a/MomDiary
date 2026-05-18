"""T016 + T017: end-to-end session continuity via X-Session-ID header.

Uses a tiny history-aware extension of the scripted agent so the test can
exercise the full POST /v1/entries → SessionStore → dispatcher → tool path.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.agents.dispatcher import AgentRunResult
from momdiary.agents.tools.registry import invoke_tool
from momdiary.api.dependencies import get_agent_runner
from tests.conftest import ScriptedAgent


class _HistoryAwareScriptedAgent(ScriptedAgent):
    """Adds a single rule for T016: when history shows a prior feed and the new
    message looks like "make it N", auto-emit an `update_feed(entry_id, quantity=N)`
    instead of consuming the scripted queue.
    """

    _make_it_re = re.compile(r"make it (\d+)", re.IGNORECASE)

    async def run(
        self,
        message: str,
        *,
        session: AsyncSession,
        correlation_id: str,
        entry_id: int | None = None,
        entry_type: str | None = None,
        history: list[Any] | None = None,
    ) -> AgentRunResult:
        m = self._make_it_re.search(message)
        if m and history:
            prior_feed_entry_id: int | None = None
            for turn in history:
                if (
                    getattr(turn, "role", None) == "assistant"
                    and getattr(turn, "entry_type", None) == "feed"
                    and getattr(turn, "entry_id", None) is not None
                ):
                    prior_feed_entry_id = turn.entry_id
            if prior_feed_entry_id is not None:
                quantity = int(m.group(1))
                self.calls.append(
                    {
                        "message": message,
                        "correlation_id": correlation_id,
                        "entry_id": entry_id,
                        "entry_type": entry_type,
                        "history": list(history),
                        "history_resolved_entry_id": prior_feed_entry_id,
                    }
                )
                return await invoke_tool(
                    "update_feed",
                    session,
                    entry_id=prior_feed_entry_id,
                    quantity=quantity,
                )
        return await super().run(
            message,
            session=session,
            correlation_id=correlation_id,
            entry_id=entry_id,
            entry_type=entry_type,
            history=history,
        )


@pytest.fixture
def history_aware_agent() -> _HistoryAwareScriptedAgent:
    return _HistoryAwareScriptedAgent()


@pytest_asyncio.fixture
async def continuity_client(
    configured_app: Any, history_aware_agent: _HistoryAwareScriptedAgent
) -> AsyncIterator[AsyncClient]:
    configured_app.dependency_overrides[get_agent_runner] = lambda: history_aware_agent
    async with AsyncClient(
        transport=ASGITransport(app=configured_app), base_url="http://test"
    ) as c:
        yield c
    configured_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_turn2_with_shared_session_id_updates_prior_entry(
    continuity_client: AsyncClient,
    history_aware_agent: _HistoryAwareScriptedAgent,
) -> None:
    """T016 / US1 happy path: shared X-Session-ID makes turn 2 reference turn 1."""
    history_aware_agent.script(
        "log_feed",
        feed_type="breast_milk",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )

    r1 = await continuity_client.post(
        "/v1/entries",
        json={"message": "120 ml breast milk just now"},
    )
    assert r1.status_code == 201, r1.text
    body1 = r1.json()
    assert body1["outcome"] == "created"
    assert body1["entry_type"] == "feed"
    e1_id = body1["entry"]["id"]
    session_id = r1.headers["X-Session-ID"]
    assert body1["session_id"] == session_id

    r2 = await continuity_client.post(
        "/v1/entries",
        json={"message": "actually make it 90"},
        headers={"X-Session-ID": session_id},
    )
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["outcome"] == "updated"
    assert body2["entry_type"] == "feed"
    assert body2["entry"]["id"] == e1_id
    assert body2["entry"]["quantity"] == 90
    assert body2["session_id"] == session_id
    assert r2.headers["X-Session-ID"] == session_id

    # The history-aware agent must have observed the turn-1 assistant turn.
    last_call = history_aware_agent.calls[-1]
    assert last_call["history_resolved_entry_id"] == e1_id
    history_texts = [getattr(t, "text", "") for t in last_call["history"]]
    assert any("120" in t for t in history_texts)


@pytest.mark.asyncio
async def test_turn2_without_session_id_starts_fresh_session(
    continuity_client: AsyncClient,
    history_aware_agent: _HistoryAwareScriptedAgent,
) -> None:
    """T017 / negative path: missing X-Session-ID on turn 2 → fresh session."""
    history_aware_agent.script(
        "log_feed",
        feed_type="breast_milk",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    ).script(
        "ask_for_clarification",
        question="Which feed should I update?",
    )

    r1 = await continuity_client.post(
        "/v1/entries",
        json={"message": "120 ml breast milk just now"},
    )
    assert r1.status_code == 201
    sid1 = r1.headers["X-Session-ID"]

    r2 = await continuity_client.post(
        "/v1/entries",
        json={"message": "actually make it 90"},
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["outcome"] == "clarification_requested"
    sid2 = r2.headers["X-Session-ID"]
    assert sid2 != sid1
    assert body2["session_id"] == sid2

    # And the history-aware rule did not fire because history was empty on turn 2.
    last_call = history_aware_agent.calls[-1]
    assert last_call["history"] == []
