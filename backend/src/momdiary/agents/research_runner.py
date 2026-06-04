"""``ResearchRunner`` — orchestrates one research turn end-to-end (feature 011).

Responsibilities:

1. Resolve or mint a chat session under the caller's (user_id, baby_id)
   partition (feature 003 + 009).
2. Persist the caregiver turn before the upstream call so a crash
   mid-call doesn't lose user input (FR-022).
3. Invoke the injected :class:`WebSearchPort` under a hard timeout
   (FR-014). Any timeout or upstream exception maps to
   ``outcome="research_unavailable"`` — the assistant turn is still
   persisted for transcript fidelity.
4. Apply `clamp_sources` and normalize the assistant message.
5. Persist the assistant turn (including the optional ``sources`` list).
6. Return a :class:`ResearchRunResult` that the API layer renders to
   JSON 1:1.

The runner is deliberately *not* MAF-aware — all MAF interaction lives
behind the ``WebSearchPort`` interface so tests can drop in a
deterministic stub without spinning up MAF.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from momdiary.agents.research_agent import (
    ResearchUnavailableError,
    WebSearchPort,
)
from momdiary.agents.research_policy import (
    CANNED_MESSAGES,
    ResearchOutcome,
    clamp_sources,
    ensure_disclaimer,
)
from momdiary.agents.session_store import ChatTurn, SessionStore
from momdiary.observability.logging import get_logger

if TYPE_CHECKING:
    from momdiary.agents.session_store import ChatSession  # noqa: F401

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Public result envelope
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ResearchRunResult:
    """Outcome of one call to :meth:`ResearchRunner.run`.

    Fields map 1:1 to the JSON response envelope documented in
    ``contracts/research-api.md``. ``sources`` is always a list — empty
    for every outcome except ``research_answer``.
    """

    outcome: ResearchOutcome
    agent_message: str
    sources: list[dict[str, str]]
    session_id: str
    correlation_id: str


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class ResearchRunner:
    """Single-method orchestrator for ``POST /v1/research``."""

    def __init__(
        self,
        *,
        web_search: WebSearchPort,
        session_store: SessionStore,
        timeout_seconds: int,
        min_sources: int,
        max_sources: int,
    ) -> None:
        if max_sources < min_sources:
            raise ValueError(
                f"max_sources ({max_sources}) must be >= min_sources ({min_sources})"
            )
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must be >= 0")
        self._web_search = web_search
        self._store = session_store
        self._timeout_seconds = timeout_seconds
        self._min_sources = min_sources
        self._max_sources = max_sources

    async def run(
        self,
        message: str,
        *,
        user_id: int,
        baby_id: int,
        baby_age_phrase: str,
        session_id: str | None,
        correlation_id: str | None,
    ) -> ResearchRunResult:
        """Execute one research turn against the configured ``WebSearchPort``."""
        cid = correlation_id or str(uuid.uuid4())
        t0 = time.perf_counter()
        session = await self._store.get_or_create(
            session_id,
            correlation_id=cid,
            user_id=user_id,
            baby_id=baby_id,
        )

        # Serialize the multi-step turn under the per-session lock so
        # concurrent calls for the same session see a consistent history.
        async with session.lock:
            await self._store.append(
                session,
                ChatTurn(
                    role="caregiver",
                    text=message,
                    correlation_id=cid,
                    created_at=_utc_now(),
                ),
            )

            (
                outcome,
                agent_message,
                sources,
                sources_before_filter,
                web_search_succeeded,
            ) = await self._invoke_web_search(
                message, age_phrase=baby_age_phrase, correlation_id=cid
            )

            await self._store.append(
                session,
                ChatTurn(
                    role="assistant",
                    text=agent_message,
                    correlation_id=cid,
                    created_at=_utc_now(),
                    outcome=outcome,
                    sources=list(sources),
                ),
            )

        latency_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(
            "research.runner.completed",
            correlation_id=cid,
            user_id=user_id,
            baby_id=baby_id,
            session_id=session.id[:8],
            outcome=outcome,
            web_search_attempted=True,
            web_search_succeeded=web_search_succeeded,
            sources_before_filter=sources_before_filter,
            sources_after_filter=len(sources),
            handler_latency_ms=latency_ms,
            message_length=len(message),
            age_value=baby_age_phrase or "",
        )

        return ResearchRunResult(
            outcome=outcome,
            agent_message=agent_message,
            sources=list(sources),
            session_id=session.id,
            correlation_id=cid,
        )

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    async def _invoke_web_search(
        self,
        message: str,
        *,
        age_phrase: str,
        correlation_id: str,
    ) -> tuple[ResearchOutcome, str, list[dict[str, str]], int, bool]:
        """Wrap the port call with timeout + error mapping.

        Returns ``(outcome, agent_message, sources, sources_before_filter,
        web_search_succeeded)``. Never raises.
        """
        try:
            if self._timeout_seconds == 0:
                # ``asyncio.wait_for(timeout=0)`` raises immediately if the
                # coroutine doesn't return synchronously — useful for
                # exercising the failure path in tests.
                synthesized, raw_sources = await asyncio.wait_for(
                    self._web_search.search(message, age_label=age_phrase),
                    timeout=0,
                )
            else:
                synthesized, raw_sources = await asyncio.wait_for(
                    self._web_search.search(message, age_label=age_phrase),
                    timeout=self._timeout_seconds,
                )
        except (TimeoutError, asyncio.TimeoutError):
            logger.warning(
                "research.web_search.timeout",
                correlation_id=correlation_id,
                timeout_seconds=self._timeout_seconds,
            )
            return (
                "research_unavailable",
                CANNED_MESSAGES["research_unavailable"],
                [],
                0,
                False,
            )
        except ResearchUnavailableError as exc:
            logger.warning(
                "research.web_search.unavailable",
                correlation_id=correlation_id,
                reason=str(exc),
            )
            return (
                "research_unavailable",
                CANNED_MESSAGES["research_unavailable"],
                [],
                0,
                False,
            )
        except Exception as exc:  # noqa: BLE001 — never propagate to the user
            logger.exception(
                "research.web_search.unexpected_error",
                correlation_id=correlation_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return (
                "research_unavailable",
                CANNED_MESSAGES["research_unavailable"],
                [],
                0,
                False,
            )

        clamped = clamp_sources(
            raw_sources, min_n=self._min_sources, max_n=self._max_sources
        )
        sources_before_filter = len(raw_sources)
        if not clamped:
            return (
                "no_sources_found",
                CANNED_MESSAGES["no_sources_found"],
                [],
                sources_before_filter,
                True,
            )

        agent_message = ensure_disclaimer(synthesized or "")
        return (
            "research_answer",
            agent_message,
            clamped,
            sources_before_filter,
            True,
        )


def _utc_now() -> datetime:
    return datetime.now(UTC)


__all__ = ["ResearchRunResult", "ResearchRunner"]
