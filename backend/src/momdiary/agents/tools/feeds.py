"""MAF tool implementations for `feeds` (FR-003, FR-015, FR-018)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.agents.dispatcher import AgentRunResult
from momdiary.agents.tools._dedup import find_same_minute
from momdiary.db.repositories.feeds import FeedsRepository
from momdiary.models.orm import Feed
from momdiary.models.schemas import FeedEntry
from momdiary.observability.logging import get_logger
from momdiary.services.time_service import (
    get_default_timezone,
    parse_iso_with_offset,
)

logger = get_logger(__name__)


def _to_entry(row: Feed) -> dict:
    return FeedEntry.model_validate(
        {
            "id": row.id,
            "feed_type": row.feed_type,
            "quantity": row.quantity,
            "unit": row.unit,
            "occurred_at": row.occurred_at,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
    ).model_dump(mode="json")


# --- argument schemas (also used by the contract tests) -------------------


class LogFeedArgs(BaseModel):
    feed_type: Literal["breast_milk", "formula", "solids", "water"]
    quantity: Annotated[float, Field(gt=0)]
    unit: Literal["ml", "g"]
    occurred_at: str


class UpdateFeedArgs(BaseModel):
    entry_id: int
    feed_type: Literal["breast_milk", "formula", "solids", "water"] | None = None
    quantity: Annotated[float, Field(gt=0)] | None = None
    unit: Literal["ml", "g"] | None = None
    occurred_at: str | None = None


class DeleteFeedArgs(BaseModel):
    entry_id: int


# --- tool functions --------------------------------------------------------


async def log_feed(
    session: AsyncSession,
    *,
    feed_type: str,
    quantity: float,
    unit: str,
    occurred_at: str,
) -> AgentRunResult:
    args = LogFeedArgs.model_validate(
        {
            "feed_type": feed_type,
            "quantity": quantity,
            "unit": unit,
            "occurred_at": occurred_at,
        }
    )
    repo = FeedsRepository(session)

    # Same-minute dedup -> route to update_feed automatically. Replaces the
    # old prompt rule that asked the LLM to list_feeds first.
    try:
        target_local_date = (
            parse_iso_with_offset(args.occurred_at)
            .astimezone(await get_default_timezone(session))
            .date()
        )
        existing = await repo.list_by_date(target_local_date)
        dup = find_same_minute(existing, args.occurred_at, lambda r: r.occurred_at)
    except ValueError:
        dup = None  # let the repo's validation raise the canonical error

    if dup is not None:
        logger.info(
            "feeds.log.deduped_to_update",
            existing_id=dup.id,
            occurred_at=args.occurred_at,
        )
        row, unchanged = await repo.update(
            dup.id,
            feed_type=args.feed_type,
            quantity=args.quantity,
            unit=args.unit,
            occurred_at=args.occurred_at,
        )
        assert row is not None  # row came from list_by_date moments ago
        return AgentRunResult(
            selected_tool="log_feed",
            outcome="updated",
            entry_type="feed",
            entry_id=row.id,
            payload=_to_entry(row),
            agent_message=(
                "No changes were needed."
                if unchanged
                else f"Updated existing feed to {row.quantity} {row.unit} of {row.feed_type}."
            ),
            unchanged=unchanged,
        )

    row = await repo.create(**args.model_dump())
    return AgentRunResult(
        selected_tool="log_feed",
        outcome="created",
        entry_type="feed",
        entry_id=row.id,
        payload=_to_entry(row),
        agent_message=f"Logged {row.quantity} {row.unit} of {row.feed_type}.",
    )


async def update_feed(
    session: AsyncSession,
    *,
    entry_id: int,
    feed_type: str | None = None,
    quantity: float | None = None,
    unit: str | None = None,
    occurred_at: str | None = None,
) -> AgentRunResult:
    args = UpdateFeedArgs.model_validate(
        {
            "entry_id": entry_id,
            "feed_type": feed_type,
            "quantity": quantity,
            "unit": unit,
            "occurred_at": occurred_at,
        }
    )
    repo = FeedsRepository(session)
    row, unchanged = await repo.update(
        args.entry_id,
        feed_type=args.feed_type,
        quantity=args.quantity,
        unit=args.unit,
        occurred_at=args.occurred_at,
    )
    if row is None:
        return AgentRunResult(
            selected_tool="update_feed",
            outcome="rejected",
            entry_type="feed",
            agent_message=f"Feed {entry_id} not found.",
        )
    return AgentRunResult(
        selected_tool="update_feed",
        outcome="updated",
        entry_type="feed",
        entry_id=row.id,
        payload=_to_entry(row),
        agent_message="No changes were needed." if unchanged else "Feed updated.",
        unchanged=unchanged,
    )


async def delete_feed(session: AsyncSession, *, entry_id: int) -> AgentRunResult:
    repo = FeedsRepository(session)
    row = await repo.soft_delete(entry_id)
    if row is None:
        return AgentRunResult(
            selected_tool="delete_feed",
            outcome="rejected",
            entry_type="feed",
            agent_message=f"Feed {entry_id} not found.",
        )
    return AgentRunResult(
        selected_tool="delete_feed",
        outcome="deleted",
        entry_type="feed",
        entry_id=row.id,
        payload=_to_entry(row),
        agent_message="Feed removed.",
    )
