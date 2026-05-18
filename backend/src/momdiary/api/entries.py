"""POST/PUT `/v1/entries` — single conversational write endpoint."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.agents.dispatcher import AgentDispatcher, AgentRunner, AgentRunResult
from momdiary.agents.session_store import (
    ChatTurn,
    SessionMessageTooLargeError,
    SessionStore,
)
from momdiary.agents.tools.registry import invoke_tool
from momdiary.api.dependencies import (
    build_response_envelope,
    get_dispatcher,
    get_session_store,
)
from momdiary.config import get_settings
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


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _assistant_turn_from_result(
    *, dispatch_result, correlation_id: str
) -> ChatTurn:
    """Derive an assistant ChatTurn from the dispatcher's result envelope."""
    res = dispatch_result.result
    if res.outcome == "clarification_requested":
        text = res.agent_message or "Could you clarify?"
        return ChatTurn(
            role="assistant",
            text=text,
            correlation_id=correlation_id,
            created_at=_utc_now(),
            outcome="clarification_requested",
        )
    if res.outcome == "rejected":
        text = res.agent_message or "Request rejected."
        return ChatTurn(
            role="assistant",
            text=text,
            correlation_id=correlation_id,
            created_at=_utc_now(),
            outcome="rejected",
        )
    # write outcome: created/updated/deleted
    text = res.agent_message or f"{res.outcome} {res.entry_type}."
    return ChatTurn(
        role="assistant",
        text=text,
        correlation_id=correlation_id,
        created_at=_utc_now(),
        outcome=res.outcome,
        entry_type=res.entry_type,
        entry_id=res.entry_id,
    )


def _truncate_for_log(value: str | None) -> str:
    if not value:
        return ""
    return value[:8]


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
        history: list[ChatTurn] | None = None,
    ) -> AgentRunResult:
        # history intentionally ignored: this path is a deterministic single
        # tool invocation that the model never sees.
        kwargs = dict(self._tool_kwargs)
        if entry_id is not None and "entry_id" not in kwargs:
            kwargs["entry_id"] = entry_id
        return await invoke_tool(self._tool_name, session, **kwargs)


@router.post("/entries")
async def create_entry(
    payload: AgentWriteRequest,
    response: Response,
    dispatcher: Annotated[AgentDispatcher, Depends(get_dispatcher)],
    store: Annotated[SessionStore, Depends(get_session_store)],
    x_session_id: Annotated[str | None, Header(alias="X-Session-ID")] = None,
) -> dict:
    """T034 / T035: agent-routed creation; clarification short-circuits to 200."""
    cid = _correlation_id(payload)
    logger.info(
        "entries.post.received",
        correlation_id=cid,
        message_len=len(payload.message),
        hinted_entry_type=payload.entry_type,
        hinted_entry_id=payload.entry_id,
        session_id_present=x_session_id is not None,
    )
    chat_session = await store.get_or_create(x_session_id, correlation_id=cid)
    settings = get_settings()
    async with chat_session.lock:
        history = await store.recent_view(
            chat_session,
            token_budget=settings.momdiary_session_prompt_token_budget,
        )
        caregiver_turn = ChatTurn(
            role="caregiver",
            text=payload.message,
            correlation_id=cid,
            created_at=_utc_now(),
        )
        try:
            await store.append(chat_session, caregiver_turn)
        except SessionMessageTooLargeError as exc:
            logger.warning(
                "session.message_too_large",
                correlation_id=cid,
                session_id=_truncate_for_log(chat_session.id),
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "validation_error",
                    "message": str(exc),
                    "correlation_id": cid,
                    "session_id": chat_session.id,
                },
            ) from exc
        except Exception:  # FR-016: store failures must not break the HTTP response
            logger.warning(
                "session.append_failed",
                correlation_id=cid,
                session_id=_truncate_for_log(chat_session.id),
                exc_info=True,
            )
        result = await dispatcher.dispatch(
            message=payload.message,
            correlation_id=cid,
            entry_id=payload.entry_id,
            entry_type=payload.entry_type,
            history=history,
        )
        try:
            await store.append(
                chat_session,
                _assistant_turn_from_result(
                    dispatch_result=result, correlation_id=cid
                ),
            )
        except SessionMessageTooLargeError:
            logger.warning(
                "session.assistant_turn_dropped",
                correlation_id=cid,
                session_id=_truncate_for_log(chat_session.id),
            )
        except Exception:  # FR-016: store failures must not break the HTTP response
            logger.warning(
                "session.append_failed",
                correlation_id=cid,
                session_id=_truncate_for_log(chat_session.id),
                exc_info=True,
            )

    status, body = build_response_envelope(
        result, session_id=chat_session.id
    )
    response.status_code = status
    response.headers["X-Session-ID"] = chat_session.id
    return body


@router.put("/entries")
async def update_or_delete_entry(
    payload: AgentWriteRequest,
    response: Response,
    dispatcher: Annotated[AgentDispatcher, Depends(get_dispatcher)],
    session: Annotated[AsyncSession, Depends(get_session)],
    store: Annotated[SessionStore, Depends(get_session_store)],
    x_session_id: Annotated[str | None, Header(alias="X-Session-ID")] = None,
) -> dict:
    """T068: deterministic update path when (entry_id, entry_type) supplied.

    T069: when the repository reports the row is unchanged, the response
    body is byte-identical to the previous PUT (FR-015).
    """
    cid = _correlation_id(payload)
    chat_session = await store.get_or_create(x_session_id, correlation_id=cid)
    settings = get_settings()

    async with chat_session.lock:
        history = await store.recent_view(
            chat_session,
            token_budget=settings.momdiary_session_prompt_token_budget,
        )
        caregiver_turn = ChatTurn(
            role="caregiver",
            text=payload.message,
            correlation_id=cid,
            created_at=_utc_now(),
        )
        try:
            await store.append(chat_session, caregiver_turn)
        except SessionMessageTooLargeError as exc:
            logger.warning(
                "session.message_too_large",
                correlation_id=cid,
                session_id=_truncate_for_log(chat_session.id),
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "validation_error",
                    "message": str(exc),
                    "correlation_id": cid,
                    "session_id": chat_session.id,
                },
            ) from exc
        except Exception:  # FR-016: store failures must not break the HTTP response
            logger.warning(
                "session.append_failed",
                correlation_id=cid,
                session_id=_truncate_for_log(chat_session.id),
                exc_info=True,
            )

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
                        "session_id": chat_session.id,
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
                        "session_id": chat_session.id,
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
                history=history,
            )
        else:
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
                history=history,
            )

        try:
            await store.append(
                chat_session,
                _assistant_turn_from_result(
                    dispatch_result=result, correlation_id=cid
                ),
            )
        except SessionMessageTooLargeError:
            logger.warning(
                "session.assistant_turn_dropped",
                correlation_id=cid,
                session_id=_truncate_for_log(chat_session.id),
            )
        except Exception:  # FR-016
            logger.warning(
                "session.append_failed",
                correlation_id=cid,
                session_id=_truncate_for_log(chat_session.id),
                exc_info=True,
            )

    status, body = build_response_envelope(
        result, session_id=chat_session.id
    )
    if status == 201:
        status = 200
    response.status_code = status
    response.headers["X-Session-ID"] = chat_session.id
    return body
