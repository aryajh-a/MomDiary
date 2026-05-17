"""HTTP endpoint dependencies + agent factory wiring.

Tests override `get_agent_runner` via `app.dependency_overrides` to inject
the deterministic scripted agent (Principle II).
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.agents.dispatcher import AgentDispatcher, AgentRunner
from momdiary.db.engine import get_session


async def get_agent_runner() -> AgentRunner:  # pragma: no cover - replaced in tests
    """Build the real MAF-backed agent runner.

    Imported lazily so test environments need not install MAF.
    """
    from momdiary.agents.maf_runner import MAFAgentRunner

    return MAFAgentRunner()


async def get_dispatcher(
    agent: AgentRunner = Depends(get_agent_runner),
    session: AsyncSession = Depends(get_session),
) -> AgentDispatcher:
    return AgentDispatcher(agent=agent, session=session)


def build_response_envelope(
    dispatch_result: Any,
) -> tuple[int, dict[str, Any]]:
    """Translate an `AgentDispatcher.dispatch()` result into (status, body)."""
    res = dispatch_result.result
    cid = dispatch_result.correlation_id

    if res.outcome == "clarification_requested":
        body = {
            "outcome": "clarification_requested",
            "agent_message": res.agent_message or "Could you clarify?",
            "correlation_id": cid,
        }
        if res.suggested_candidates:
            body["suggested_candidates"] = res.suggested_candidates
        return 200, body

    if res.outcome == "rejected":
        body = {
            "error": "not_found" if res.entry_id else "validation_error",
            "message": res.agent_message or "Request rejected.",
            "correlation_id": cid,
        }
        return 404 if res.entry_id else 400, body

    status_map = {"created": 201, "updated": 200, "deleted": 200}
    status = status_map.get(res.outcome, 200)
    body = {
        "outcome": res.outcome,
        "entry_type": res.entry_type,
        "entry": res.payload,
        "agent_message": res.agent_message,
        "correlation_id": cid,
    }
    return status, body
