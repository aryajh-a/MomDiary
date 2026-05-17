"""POST/PUT `/v1/entries` — single conversational write endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.agents.dispatcher import AgentDispatcher, AgentRunner, AgentRunResult
from momdiary.agents.tools.registry import invoke_tool
from momdiary.api.dependencies import build_response_envelope, get_dispatcher
from momdiary.db.engine import get_session
from momdiary.models.schemas import AgentWriteRequest
from momdiary.observability.logging import get_logger
from momdiary.observability.middleware import current_correlation_id
from momdiary.services.target_resolver import resolve

logger = get_logger(__name__)

router = APIRouter(tags=["entries"])

_UPDATE_TOOLS = {
    "feed": "update_feed",
    "sleep": "update_sleep",
    "poop": "update_poop",
    "appointment": "update_appointment",
}


def _correlation_id(req: AgentWriteRequest) -> str:
    return req.correlation_id or current_correlation_id() or "unknown"


class _DirectToolRunner:
    """Bypass the model: invoke a named tool deterministically (T068)."""

    def __init__(self, tool_name: str, **tool_kwargs: object) -> None:
        self._tool_name = tool_name
        self._tool_kwargs = tool_kwargs

    async def run(
        self,
        message: str,
        *,
        session: AsyncSession,
        correlation_id: str,
        entry_id: int | None = None,
        entry_type: str | None = None,
    ) -> AgentRunResult:
        kwargs = dict(self._tool_kwargs)
        if entry_id is not None and "entry_id" not in kwargs:
            kwargs["entry_id"] = entry_id
        return await invoke_tool(self._tool_name, session, **kwargs)


@router.post("/entries")
async def create_entry(
    payload: AgentWriteRequest,
    response: Response,
    dispatcher: Annotated[AgentDispatcher, Depends(get_dispatcher)],
) -> dict:
    """T034 / T035: agent-routed creation; clarification short-circuits to 200."""
    logger.info(
        "entries.post.received",
        correlation_id=_correlation_id(payload),
        message_len=len(payload.message),
        hinted_entry_type=payload.entry_type,
        hinted_entry_id=payload.entry_id,
    )
    result = await dispatcher.dispatch(
        message=payload.message,
        correlation_id=_correlation_id(payload),
        entry_id=payload.entry_id,
        entry_type=payload.entry_type,
    )
    status, body = build_response_envelope(result)
    response.status_code = status
    return body


@router.put("/entries")
async def update_or_delete_entry(
    payload: AgentWriteRequest,
    response: Response,
    dispatcher: Annotated[AgentDispatcher, Depends(get_dispatcher)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """T068: deterministic update path when (entry_id, entry_type) supplied.

    T069: when the repository reports the row is unchanged, the response
    body is byte-identical to the previous PUT (FR-015).
    """
    cid = _correlation_id(payload)

    if payload.entry_id is not None and payload.entry_type is not None:
        logger.info(
            "entries.put.received",
            correlation_id=cid,
            branch="direct",
            entry_type=payload.entry_type,
            entry_id=payload.entry_id,
        )
        if payload.entry_type not in _UPDATE_TOOLS:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "validation_error",
                    "message": f"Unknown entry_type: {payload.entry_type}",
                    "correlation_id": cid,
                },
            )
        resolution = await resolve(
            session,
            hinted_id=payload.entry_id,
            hinted_type=payload.entry_type,
        )
        if not resolution.is_resolved:
            logger.info(
                "entries.put.not_found",
                correlation_id=cid,
                entry_type=payload.entry_type,
                entry_id=payload.entry_id,
            )
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": (
                        f"{payload.entry_type} {payload.entry_id} not found "
                        "or already deleted."
                    ),
                    "correlation_id": cid,
                },
            )
        tool_name = _UPDATE_TOOLS[payload.entry_type]
        runner: AgentRunner = _DirectToolRunner(tool_name)
        direct_dispatcher = AgentDispatcher(agent=runner, session=session)
        result = await direct_dispatcher.dispatch(
            message=payload.message,
            correlation_id=cid,
            entry_id=payload.entry_id,
            entry_type=payload.entry_type,
        )
        status, body = build_response_envelope(result)
        if status == 201:  # PUT never creates
            status = 200
        response.status_code = status
        return body

    # Conversational branch — delegated to the agent.
    logger.info(
        "entries.put.received",
        correlation_id=cid,
        branch="conversational",
        hinted_entry_type=payload.entry_type,
        hinted_entry_id=payload.entry_id,
    )
    result = await dispatcher.dispatch(
        message=payload.message,
        correlation_id=cid,
        entry_id=payload.entry_id,
        entry_type=payload.entry_type,
    )
    status, body = build_response_envelope(result)
    if status == 201:
        status = 200
    response.status_code = status
    return body
