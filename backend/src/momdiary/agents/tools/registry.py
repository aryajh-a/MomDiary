"""Registry mapping tool names to their async implementations.

Used by the scripted test agent and by the real MAF wiring (T033, T067)
to register the same set of callables on the ChatAgent.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.agents.dispatcher import AgentRunResult
from momdiary.agents.tools import appointments, feeds, poops, reads, sleeps
from momdiary.observability.logging import get_logger

logger = get_logger(__name__)

ToolFn = Callable[..., Awaitable[AgentRunResult]]
ReadToolFn = Callable[..., Awaitable[dict[str, Any]]]

TOOL_REGISTRY: dict[str, ToolFn] = {
    # log_*
    "log_feed": feeds.log_feed,
    "log_sleep": sleeps.log_sleep,
    "log_poop": poops.log_poop,
    "log_appointment": appointments.log_appointment,
    # update_*
    "update_feed": feeds.update_feed,
    "update_sleep": sleeps.update_sleep,
    "update_poop": poops.update_poop,
    "update_appointment": appointments.update_appointment,
    # delete_*
    "delete_feed": feeds.delete_feed,
    "delete_sleep": sleeps.delete_sleep,
    "delete_poop": poops.delete_poop,
    "delete_appointment": appointments.delete_appointment,
    # notes
    "add_appointment_note": appointments.add_appointment_note,
}

# Read-only tools. Kept separate because they return raw data dicts rather
# than `AgentRunResult` envelopes and must NOT be treated as the final
# write outcome by the runner.
READ_TOOL_REGISTRY: dict[str, ReadToolFn] = {
    "list_feeds": reads.list_feeds,
    "list_sleeps": reads.list_sleeps,
    "list_poops": reads.list_poops,
    "list_appointments": reads.list_appointments,
}


async def invoke_tool(
    name: str, session: AsyncSession, **kwargs: Any
) -> AgentRunResult:
    logger.info("tool.invoking", tool=name, args=list(kwargs.keys()))
    if name == "ask_for_clarification":
        logger.info("tool.clarification", tool=name)
        return AgentRunResult(
            selected_tool=name,
            outcome="clarification_requested",
            agent_message=kwargs.get("question", "Could you clarify?"),
            suggested_candidates=kwargs.get("suggested_candidates"),
        )
    if name not in TOOL_REGISTRY:
        logger.error("tool.unknown", tool=name)
        raise KeyError(f"Unknown tool: {name}")
    try:
        result = await TOOL_REGISTRY[name](session, **kwargs)
    except Exception:
        logger.exception("tool.failed", tool=name)
        raise
    logger.info(
        "tool.completed",
        tool=name,
        outcome=result.outcome,
        entry_id=result.entry_id,
        unchanged=result.unchanged,
    )
    return result
