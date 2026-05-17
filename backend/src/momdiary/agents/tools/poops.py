"""MAF tool implementations for `poops`."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.agents.dispatcher import AgentRunResult
from momdiary.db.repositories.poops import PoopsRepository
from momdiary.models.orm import Poop
from momdiary.models.schemas import PoopEntry


def _to_entry(row: Poop) -> dict:
    return PoopEntry.model_validate(
        {
            "id": row.id,
            "occurred_at": row.occurred_at,
            "consistency": row.consistency,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
    ).model_dump(mode="json")


class LogPoopArgs(BaseModel):
    occurred_at: str
    consistency: Literal["watery", "soft", "formed", "hard"]


class UpdatePoopArgs(BaseModel):
    entry_id: int
    occurred_at: str | None = None
    consistency: Literal["watery", "soft", "formed", "hard"] | None = None


class DeletePoopArgs(BaseModel):
    entry_id: int


async def log_poop(
    session: AsyncSession, *, occurred_at: str, consistency: str
) -> AgentRunResult:
    args = LogPoopArgs(occurred_at=occurred_at, consistency=consistency)
    repo = PoopsRepository(session)
    row = await repo.create(**args.model_dump())
    return AgentRunResult(
        selected_tool="log_poop",
        outcome="created",
        entry_type="poop",
        entry_id=row.id,
        payload=_to_entry(row),
        agent_message=f"Logged {row.consistency} diaper.",
    )


async def update_poop(
    session: AsyncSession,
    *,
    entry_id: int,
    occurred_at: str | None = None,
    consistency: str | None = None,
) -> AgentRunResult:
    args = UpdatePoopArgs(
        entry_id=entry_id, occurred_at=occurred_at, consistency=consistency
    )
    repo = PoopsRepository(session)
    row, unchanged = await repo.update(
        args.entry_id, occurred_at=args.occurred_at, consistency=args.consistency
    )
    if row is None:
        return AgentRunResult(
            selected_tool="update_poop",
            outcome="rejected",
            entry_type="poop",
            agent_message=f"Poop {entry_id} not found.",
        )
    return AgentRunResult(
        selected_tool="update_poop",
        outcome="updated",
        entry_type="poop",
        entry_id=row.id,
        payload=_to_entry(row),
        agent_message="No changes were needed." if unchanged else "Poop updated.",
        unchanged=unchanged,
    )


async def delete_poop(session: AsyncSession, *, entry_id: int) -> AgentRunResult:
    repo = PoopsRepository(session)
    row = await repo.soft_delete(entry_id)
    if row is None:
        return AgentRunResult(
            selected_tool="delete_poop",
            outcome="rejected",
            entry_type="poop",
            agent_message=f"Poop {entry_id} not found.",
        )
    return AgentRunResult(
        selected_tool="delete_poop",
        outcome="deleted",
        entry_type="poop",
        entry_id=row.id,
        payload=_to_entry(row),
        agent_message="Poop removed.",
    )
