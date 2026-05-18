"""T030 / US3: Session-store append failures must not break the HTTP response.

When `store.append` raises, the response still surfaces the normal write
outcome AND a `session.append_failed` WARN log is emitted (FR-016).
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from momdiary.agents.session_store import InMemorySessionStore
from tests.conftest import ScriptedAgent


@pytest.mark.asyncio
async def test_append_failure_does_not_break_response(
    client: AsyncClient,
    scripted_agent: ScriptedAgent,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scripted_agent.script(
        "log_feed",
        feed_type="breast_milk",
        quantity=120,
        unit="ml",
        occurred_at="2026-05-16T08:00:00-07:00",
    )

    async def _boom(self: Any, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError("append failed")

    monkeypatch.setattr(InMemorySessionStore, "append", _boom)

    r = await client.post(
        "/v1/entries", json={"message": "120 ml breast milk now"}
    )

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["outcome"] == "created"
    assert body["entry_type"] == "feed"
    assert body["session_id"]

    # structlog writes JSON to stdout (PrintLoggerFactory).
    out = capsys.readouterr().out
    assert "session.append_failed" in out, (
        f"expected session.append_failed in structlog output, got:\n{out}"
    )
