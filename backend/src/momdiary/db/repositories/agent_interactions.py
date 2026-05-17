"""Repository for agent_interactions (FR-013). Insert-only."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.models.orm import AgentInteraction


@dataclass(slots=True)
class AgentInteractionRecord:
    correlation_id: str
    inbound_message: str
    outcome: str
    latency_ms: int
    selected_tool: str | None = None
    entry_type: str | None = None
    entry_id: int | None = None
    model_latency_ms: int | None = None


class AgentInteractionsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(self, record: AgentInteractionRecord) -> AgentInteraction:
        row = AgentInteraction(
            correlation_id=record.correlation_id,
            inbound_message=record.inbound_message,
            selected_tool=record.selected_tool,
            entry_type=record.entry_type,
            entry_id=record.entry_id,
            outcome=record.outcome,
            latency_ms=record.latency_ms,
            model_latency_ms=record.model_latency_ms,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_by_correlation_id(self, correlation_id: str) -> list[AgentInteraction]:
        result = await self._session.execute(
            select(AgentInteraction)
            .where(AgentInteraction.correlation_id == correlation_id)
            .order_by(AgentInteraction.id.asc())
        )
        return list(result.scalars().all())
