"""Placeholder ``/v1/research`` endpoint.

This is a stub web-research surface to let the frontend wire its Research
chat mode end-to-end. It does *not* perform real web search and intentionally
binds no diary tools — it only echoes a canned acknowledgement plus a small
list of fake citations so the UI can render the "Sources" affordance.

When a real research agent is introduced (e.g. an MAF agent with a
``web_search`` tool), this module should be replaced with a thin dispatcher
that calls it, mirroring the structure of :mod:`momdiary.api.entries`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Response
from pydantic import BaseModel, Field

from momdiary.auth.dependencies import ActiveBabyDep, CurrentUserDep
from momdiary.observability.logging import get_logger
from momdiary.observability.middleware import current_correlation_id

logger = get_logger(__name__)

router = APIRouter(tags=["research"])


class ResearchRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    correlation_id: str | None = None


class ResearchSource(BaseModel):
    title: str
    url: str


class ResearchResponse(BaseModel):
    outcome: str = "research_answer"
    agent_message: str
    sources: list[ResearchSource]
    correlation_id: str
    session_id: str | None = None


# Static demo citations. Kept here so the placeholder is fully self-contained;
# swap with real search results when a research agent is wired in.
_DEMO_SOURCES: tuple[ResearchSource, ...] = (
    ResearchSource(
        title="AAP — Healthy Children",
        url="https://www.healthychildren.org/",
    ),
    ResearchSource(
        title="NHS — Baby health",
        url="https://www.nhs.uk/baby/",
    ),
    ResearchSource(
        title="CDC — Infant and toddler health",
        url="https://www.cdc.gov/parents/infants/index.html",
    ),
)


@router.post("/research", response_model=ResearchResponse)
async def research(
    payload: ResearchRequest,
    response: Response,
    auth: CurrentUserDep,
    baby: ActiveBabyDep,
    x_session_id: Annotated[str | None, Header(alias="X-Session-ID")] = None,
) -> ResearchResponse:
    """Stub research answer. Always succeeds; never touches the diary DB."""
    cid = payload.correlation_id or current_correlation_id() or "unknown"
    logger.info(
        "research.post.received",
        correlation_id=cid,
        message_len=len(payload.message),
        user_id=auth.user.id,
        baby_id=baby.id,
        session_id_present=x_session_id is not None,
    )
    # Echo the question into the placeholder reply so the UI clearly shows
    # the round-trip worked without implying a real answer was generated.
    preview = payload.message.strip()
    if len(preview) > 140:
        preview = preview[:137] + "..."
    agent_message = (
        f"(Research placeholder) You asked: \u201c{preview}\u201d. "
        "A real web-search agent isn't wired in yet — see the linked "
        "general resources below. This is not medical advice."
    )
    if x_session_id:
        response.headers["X-Session-ID"] = x_session_id
    return ResearchResponse(
        outcome="research_answer",
        agent_message=agent_message,
        sources=list(_DEMO_SOURCES),
        correlation_id=cid,
        session_id=x_session_id,
    )
