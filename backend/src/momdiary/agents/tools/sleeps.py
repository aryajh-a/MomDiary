"""MAF tool implementations for `sleeps`."""

from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.agents.dispatcher import AgentRunResult
from momdiary.agents.tools._dedup import find_same_minute
from momdiary.db.repositories.sleeps import SleepsRepository, duration_minutes
from momdiary.models.orm import Sleep
from momdiary.models.schemas import SleepEntry
from momdiary.observability.logging import get_logger
from momdiary.services.time_service import (
    get_default_timezone,
    parse_iso_with_offset,
)

logger = get_logger(__name__)


def _to_entry(row: Sleep) -> dict:
    return SleepEntry.model_validate(
        {
            "id": row.id,
            "start_at": row.start_at,
            "end_at": row.end_at,
            "duration_minutes": duration_minutes(row),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
    ).model_dump(mode="json")


class LogSleepArgs(BaseModel):
    start_at: str
    end_at: str


class UpdateSleepArgs(BaseModel):
    entry_id: int
    start_at: str | None = None
    end_at: str | None = None


class DeleteSleepArgs(BaseModel):
    entry_id: int


async def log_sleep(
    session: AsyncSession, *, start_at: str, end_at: str
) -> AgentRunResult:
    args = LogSleepArgs(start_at=start_at, end_at=end_at)
    repo = SleepsRepository(session)

    # Same-minute dedup on start_at -> route to update_sleep automatically.
    # Sleeps are unique by start time (per prior prompt invariant).
    try:
        target_local_date = (
            parse_iso_with_offset(args.start_at)
            .astimezone(await get_default_timezone(session))
            .date()
        )
        existing = await repo.list_by_start_date(target_local_date)
        dup = find_same_minute(existing, args.start_at, lambda r: r.start_at)
    except ValueError:
        dup = None

    if dup is not None:
        logger.info(
            "sleeps.log.deduped_to_update",
            existing_id=dup.id,
            start_at=args.start_at,
        )
        row, unchanged = await repo.update(
            dup.id, start_at=args.start_at, end_at=args.end_at
        )
        assert row is not None
        return AgentRunResult(
            selected_tool="log_sleep",
            outcome="updated",
            entry_type="sleep",
            entry_id=row.id,
            payload=_to_entry(row),
            agent_message=(
                "No changes were needed."
                if unchanged
                else f"Updated existing sleep ({duration_minutes(row)} minutes)."
            ),
            unchanged=unchanged,
        )

    row = await repo.create(**args.model_dump())
    return AgentRunResult(
        selected_tool="log_sleep",
        outcome="created",
        entry_type="sleep",
        entry_id=row.id,
        payload=_to_entry(row),
        agent_message=f"Logged {duration_minutes(row)}-minute sleep.",
    )


async def update_sleep(
    session: AsyncSession,
    *,
    entry_id: int,
    start_at: str | None = None,
    end_at: str | None = None,
) -> AgentRunResult:
    args = UpdateSleepArgs(entry_id=entry_id, start_at=start_at, end_at=end_at)
    repo = SleepsRepository(session)
    row, unchanged = await repo.update(
        args.entry_id, start_at=args.start_at, end_at=args.end_at
    )
    if row is None:
        return AgentRunResult(
            selected_tool="update_sleep",
            outcome="rejected",
            entry_type="sleep",
            agent_message=f"Sleep {entry_id} not found.",
        )
    return AgentRunResult(
        selected_tool="update_sleep",
        outcome="updated",
        entry_type="sleep",
        entry_id=row.id,
        payload=_to_entry(row),
        agent_message="No changes were needed." if unchanged else "Sleep updated.",
        unchanged=unchanged,
    )


async def delete_sleep(session: AsyncSession, *, entry_id: int) -> AgentRunResult:
    repo = SleepsRepository(session)
    row = await repo.soft_delete(entry_id)
    if row is None:
        return AgentRunResult(
            selected_tool="delete_sleep",
            outcome="rejected",
            entry_type="sleep",
            agent_message=f"Sleep {entry_id} not found.",
        )
    return AgentRunResult(
        selected_tool="delete_sleep",
        outcome="deleted",
        entry_type="sleep",
        entry_id=row.id,
        payload=_to_entry(row),
        agent_message="Sleep removed.",
    )
