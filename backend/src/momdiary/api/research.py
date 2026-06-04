"""POST /v1/research — research-mode chat (feature 011).

Replaces the placeholder stub. Delegates all orchestration to
:class:`momdiary.agents.research_runner.ResearchRunner`; this module is
purely a thin HTTP adapter that:

* validates the request body (Pydantic — see ``ResearchRequest``),
* resolves the caller and active baby from existing auth dependencies,
* derives a short ``baby_age_phrase`` from ``baby.date_of_birth`` so the
  model can scope guidance,
* invokes the runner,
* renders the result into the contract-defined JSON envelope and sets
  ``X-Session-ID`` + ``X-Correlation-ID`` headers (FR-018).

Failure modes (timeout, upstream error) never produce 5xx — they map to
``outcome="research_unavailable"`` per FR-014 to keep the chat UX
consistent.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field

from momdiary.agents.research_runner import ResearchRunner, ResearchRunResult
from momdiary.api.dependencies import get_research_runner
from momdiary.auth.dependencies import ActiveBabyDep, CurrentUserDep
from momdiary.observability.logging import get_logger
from momdiary.observability.middleware import current_correlation_id

logger = get_logger(__name__)

router = APIRouter(tags=["research"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class ResearchRequest(BaseModel):
    """Inbound payload for ``POST /v1/research``."""

    message: str = Field(min_length=1, max_length=4000)
    correlation_id: str | None = None


class ResearchSource(BaseModel):
    """One citation in the response envelope."""

    title: str
    url: str


class ResearchResponse(BaseModel):
    """Outbound payload for ``POST /v1/research`` (single shape, all outcomes)."""

    outcome: Literal[
        "research_answer",
        "research_unavailable",
        "scope_refused",
        "safety_refused",
        "no_sources_found",
    ]
    agent_message: str
    sources: list[ResearchSource]
    correlation_id: str
    session_id: str | None = None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/research", response_model=ResearchResponse)
async def research(
    payload: ResearchRequest,
    response: Response,
    auth: CurrentUserDep,
    baby: ActiveBabyDep,
    runner: Annotated[ResearchRunner, Depends(get_research_runner)],
    x_session_id: Annotated[str | None, Header(alias="X-Session-ID")] = None,
) -> ResearchResponse:
    """Run one research turn and return the contract envelope."""
    cid = payload.correlation_id or current_correlation_id() or ""
    age_phrase = _age_phrase(baby.date_of_birth)

    logger.info(
        "research.post.received",
        correlation_id=cid or "unknown",
        message_length=len(payload.message),
        user_id=auth.user.id,
        baby_id=baby.id,
        session_id_present=x_session_id is not None,
        age_unit="months" if age_phrase else "",
    )

    result: ResearchRunResult = await runner.run(
        payload.message,
        user_id=auth.user.id,
        baby_id=baby.id,
        baby_age_phrase=age_phrase,
        session_id=x_session_id,
        correlation_id=cid or None,
    )

    # Echo headers per contracts/research-api.md.
    response.headers["X-Session-ID"] = result.session_id
    response.headers["X-Correlation-ID"] = result.correlation_id

    logger.info(
        "research.post.completed",
        correlation_id=result.correlation_id,
        user_id=auth.user.id,
        baby_id=baby.id,
        session_id=result.session_id[:8] if result.session_id else "",
        outcome=result.outcome,
        sources_after_filter=len(result.sources),
    )

    return ResearchResponse(
        outcome=result.outcome,
        agent_message=result.agent_message,
        sources=[ResearchSource(**s) for s in result.sources],
        correlation_id=result.correlation_id,
        session_id=result.session_id,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _age_phrase(date_of_birth: str | None) -> str:
    """Derive a short ``"N-month-old"`` phrase from the baby's DOB.

    Returns ``""`` if the DOB is missing or unparseable. Babies older
    than 24 months render as ``"N-year-old"``.
    """
    if not date_of_birth:
        return ""
    try:
        dob = date.fromisoformat(date_of_birth)
    except ValueError:
        return ""
    today = datetime.now(timezone.utc).date()
    days = (today - dob).days
    if days < 0:
        return ""
    months = days // 30
    if months < 24:
        return f"{months}-month-old" if months >= 1 else "newborn"
    years = months // 12
    return f"{years}-year-old"


__all__ = ["ResearchRequest", "ResearchResponse", "ResearchSource", "router"]
