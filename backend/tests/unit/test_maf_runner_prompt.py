"""T015: Verify MAFAgentRunner stitches history into the prompt correctly.

Stubs `build_agent` so no Azure credentials are needed. We capture the
`full_message` passed to `bundle.agent.run` and assert the contract from
plan.md (Agent Invocation Flow).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pytest

from momdiary.agents import maf_runner as maf_runner_module
from momdiary.agents.maf_runner import MAFAgentRunner, _render_history
from momdiary.agents.session_store import ChatTurn


def _now() -> datetime:
    return datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)


@dataclass
class _FakeAgent:
    captured_messages: list[str] = field(default_factory=list)

    async def run(self, message: str) -> Any:
        self.captured_messages.append(message)

        class _Resp:
            text = "ok"

        return _Resp()


@dataclass
class _FakeBundle:
    agent: _FakeAgent


class _FakeSession:
    """Bare AsyncSession stand-in; only `get_default_timezone` consumes it."""


async def _stub_get_default_timezone(_session: Any):
    from zoneinfo import ZoneInfo

    return ZoneInfo("UTC")


@pytest.fixture
def fake_agent(monkeypatch: pytest.MonkeyPatch) -> _FakeAgent:
    agent = _FakeAgent()
    monkeypatch.setattr(
        maf_runner_module, "build_agent", lambda tools=None: _FakeBundle(agent=agent)
    )
    monkeypatch.setattr(
        maf_runner_module, "_build_tool_wrappers", lambda session, captured: []
    )
    monkeypatch.setattr(
        maf_runner_module, "get_default_timezone", _stub_get_default_timezone
    )
    return agent


async def test_full_message_includes_history_block_when_non_empty(
    fake_agent: _FakeAgent,
) -> None:
    runner = MAFAgentRunner()
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
    await runner.run(
        "make it 90",
        session=_FakeSession(),  # type: ignore[arg-type]
        correlation_id="cid-2",
        history=history,
    )
    assert len(fake_agent.captured_messages) == 1
    msg = fake_agent.captured_messages[0]
    expected_history = _render_history(history)
    assert "Conversation so far:\n" in msg
    assert expected_history in msg
    assert msg.rstrip().endswith("Caregiver said: make it 90")
    # Order: context, blank line, history block, blank line, caregiver said
    history_idx = msg.index("Conversation so far:")
    said_idx = msg.index("Caregiver said:")
    assert history_idx < said_idx


async def test_full_message_elides_history_block_when_empty(
    fake_agent: _FakeAgent,
) -> None:
    runner = MAFAgentRunner()
    await runner.run(
        "Baby drank 120 ml of breast milk at 8am.",
        session=_FakeSession(),  # type: ignore[arg-type]
        correlation_id="cid-3",
        history=[],
    )
    assert len(fake_agent.captured_messages) == 1
    msg = fake_agent.captured_messages[0]
    assert "Conversation so far" not in msg
    assert msg.rstrip().endswith(
        "Caregiver said: Baby drank 120 ml of breast milk at 8am."
    )


async def test_run_requires_history_argument(fake_agent: _FakeAgent) -> None:
    runner = MAFAgentRunner()
    with pytest.raises(AssertionError):
        await runner.run(
            "hello",
            session=_FakeSession(),  # type: ignore[arg-type]
            correlation_id="cid-x",
            history=None,
        )
