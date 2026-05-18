"""T026 / US2: Two sessions must never see each other's turns.

Each client uses its own X-Session-ID; "delete that" in one client must only
delete that client's most-recent entry. Missing header always yields a fresh id.
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


class _DeleteAwareScriptedAgent(ScriptedAgent):
    """Single rule: if message matches `delete that` AND history shows a prior
    `feed` entry, auto-emit `delete_feed(entry_id=<that-feed>)`. Otherwise
    fall back to the scripted queue.
    """

    _delete_re = re.compile(r"delete that", re.IGNORECASE)

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
        if self._delete_re.search(message) and history:
            prior_feed: int | None = None
            for turn in history:
                if (
                    getattr(turn, "role", None) == "assistant"
                    and getattr(turn, "entry_type", None) == "feed"
                    and getattr(turn, "entry_id", None) is not None
                ):
                    prior_feed = turn.entry_id
            if prior_feed is not None:
                self.calls.append(
                    {
                        "message": message,
                        "correlation_id": correlation_id,
                        "entry_id": entry_id,
                        "entry_type": entry_type,
                        "history": list(history),
                        "resolved_entry_id": prior_feed,
                    }
                )
                return await invoke_tool(
                    "delete_feed", session, entry_id=prior_feed
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
def isolation_agent() -> _DeleteAwareScriptedAgent:
    return _DeleteAwareScriptedAgent()


@pytest_asyncio.fixture
async def isolation_client(
    configured_app: Any, isolation_agent: _DeleteAwareScriptedAgent
) -> AsyncIterator[AsyncClient]:
    configured_app.dependency_overrides[get_agent_runner] = lambda: isolation_agent
    async with AsyncClient(
        transport=ASGITransport(app=configured_app), base_url="http://test"
    ) as c:
        yield c
    configured_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_two_sessions_do_not_leak(
    isolation_client: AsyncClient,
    isolation_agent: _DeleteAwareScriptedAgent,
) -> None:
    """Each client's 'delete that' targets only its own session's prior feed."""
    # Two log_feed scripts; "delete that" rule fires from history, no script needed.
    isolation_agent.script(
        "log_feed",
        feed_type="breast_milk",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    ).script(
        "log_feed",
        feed_type="formula",
        quantity=150,
        unit="ml",
        occurred_at="2026-05-16T09:00:00-07:00",
    )

    # Client A logs a breast-milk feed.
    rA1 = await isolation_client.post(
        "/v1/entries",
        json={"message": "120 ml breast milk now"},
    )
    assert rA1.status_code == 201, rA1.text
    bodyA1 = rA1.json()
    sid_A = rA1.headers["X-Session-ID"]
    feed_A = bodyA1["entry"]["id"]
    assert bodyA1["session_id"] == sid_A

    # Client B (separate session) logs a formula feed.
    rB1 = await isolation_client.post(
        "/v1/entries",
        json={"message": "150 ml formula now"},
    )
    assert rB1.status_code == 201, rB1.text
    bodyB1 = rB1.json()
    sid_B = rB1.headers["X-Session-ID"]
    feed_B = bodyB1["entry"]["id"]
    assert bodyB1["session_id"] == sid_B

    # Sessions must be distinct.
    assert sid_A != sid_B
    assert feed_A != feed_B

    # Client B deletes "that" → must hit feed_B (its own), NOT feed_A.
    rB2 = await isolation_client.post(
        "/v1/entries",
        json={"message": "delete that"},
        headers={"X-Session-ID": sid_B},
    )
    assert rB2.status_code in (200, 201), rB2.text
    bodyB2 = rB2.json()
    assert bodyB2["outcome"] == "deleted"
    assert bodyB2["entry"]["id"] == feed_B
    assert bodyB2["session_id"] == sid_B

    last_call = isolation_agent.calls[-1]
    assert last_call["resolved_entry_id"] == feed_B
    # And history passed to B's turn must NOT mention feed A's quantity.
    history_texts = [getattr(t, "text", "") for t in last_call["history"]]
    assert all("120" not in t for t in history_texts), history_texts

    # Confirm feed_A still exists (was not soft-deleted by B's call).
    feeds_resp = await isolation_client.get(
        "/v1/feeds", params={"date": "2026-05-16"}
    )
    assert feeds_resp.status_code == 200, feeds_resp.text
    feeds_ids = {e["id"] for e in feeds_resp.json().get("items", [])}
    assert feed_A in feeds_ids
    assert feed_B not in feeds_ids


@pytest.mark.asyncio
async def test_unknown_session_id_treated_as_fresh(
    isolation_client: AsyncClient,
    isolation_agent: _DeleteAwareScriptedAgent,
) -> None:
    """FR-007: an unknown X-Session-ID is honored as a fresh, empty session."""
    isolation_agent.script(
        "log_feed",
        feed_type="breast_milk",
        quantity=100,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )

    unknown_id = "00000000-0000-4000-8000-000000000000"
    r = await isolation_client.post(
        "/v1/entries",
        json={"message": "100 ml breast milk now"},
        headers={"X-Session-ID": unknown_id},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # Either the server adopts the supplied id, or issues a fresh one — both are
    # spec-compliant (FR-007). What matters: the body's session_id equals the
    # response header, and the session is treated as fresh (no history mishap).
    assert body["session_id"] == r.headers["X-Session-ID"]
    assert isolation_agent.calls[-1]["history"] == []
