"""Agent dispatcher: runs the MAF agent and audits each invocation (FR-013)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.db.repositories.agent_interactions import (
    AgentInteractionRecord,
    AgentInteractionsRepository,
)
from momdiary.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class AgentRunResult:
    """Normalized result the dispatcher receives from an agent run."""

    selected_tool: str | None
    outcome: str  # created | updated | deleted | clarification_requested | rejected
    entry_type: str | None = None
    entry_id: int | None = None
    payload: dict[str, Any] | None = None
    agent_message: str | None = None
    suggested_candidates: list[dict[str, Any]] | None = None
    model_latency_ms: int | None = None
    unchanged: bool = False  # FR-015 idempotency short-circuit (T069)


class AgentRunner(Protocol):
    """Minimal protocol the dispatcher needs from an agent."""

    async def run(
        self,
        message: str,
        *,
        session: AsyncSession,
        correlation_id: str,
        entry_id: int | None = None,
        entry_type: str | None = None,
    ) -> AgentRunResult: ...


@dataclass(slots=True)
class DispatchResult:
    result: AgentRunResult
    latency_ms: int
    correlation_id: str


class AgentDispatcher:
    """Glue between HTTP endpoints and the MAF agent."""

    def __init__(self, agent: AgentRunner, session: AsyncSession) -> None:
        self._agent = agent
        self._session = session

    async def dispatch(
        self,
        *,
        message: str,
        correlation_id: str,
        entry_id: int | None = None,
        entry_type: str | None = None,
    ) -> DispatchResult:
        logger.info(
            "dispatch.started",
            correlation_id=correlation_id,
            message_len=len(message),
            hinted_entry_id=entry_id,
            hinted_entry_type=entry_type,
        )
        started = time.perf_counter()
        try:
            result = await self._agent.run(
                message,
                session=self._session,
                correlation_id=correlation_id,
                entry_id=entry_id,
                entry_type=entry_type,
            )
        except Exception:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            logger.exception(
                "dispatch.agent_run_failed",
                correlation_id=correlation_id,
                duration_ms=elapsed_ms,
            )
            raise
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "dispatch.agent_run_completed",
            correlation_id=correlation_id,
            selected_tool=result.selected_tool,
            outcome=result.outcome,
            entry_type=result.entry_type,
            entry_id=result.entry_id,
            unchanged=result.unchanged,
            duration_ms=elapsed_ms,
        )

        repo = AgentInteractionsRepository(self._session)
        await repo.insert(
            AgentInteractionRecord(
                correlation_id=correlation_id,
                inbound_message=message,
                selected_tool=result.selected_tool,
                entry_type=result.entry_type,
                entry_id=result.entry_id,
                outcome=result.outcome,
                latency_ms=elapsed_ms,
                model_latency_ms=result.model_latency_ms,
            )
        )
        await self._session.commit()
        logger.debug(
            "dispatch.audit_recorded",
            correlation_id=correlation_id,
            selected_tool=result.selected_tool,
            outcome=result.outcome,
        )
        return DispatchResult(
            result=result, latency_ms=elapsed_ms, correlation_id=correlation_id
        )
