"""Research agent + web-search port (feature 011, Brave Search backend).

Public contract:

* :class:`WebSearchPort` — narrow ``Protocol`` consumed by
  :class:`momdiary.agents.research_runner.ResearchRunner`. Tests inject
  stubs that satisfy this interface, so the runner is fully
  port-agnostic.

* :class:`ResearchUnavailableError` — raised by ``WebSearchPort.search``
  when the upstream cannot answer (HTTP error, quota, missing config).
  The runner catches it and maps to ``outcome="research_unavailable"``
  per FR-014.

* :class:`BraveResearchAdapter` — production implementation. It builds a
  per-request MAF :class:`Agent` backed by the existing Azure OpenAI
  chat client (same APIM-fronted deployment the diary agent uses, see
  :mod:`momdiary.agents.diary_agent`) and registers a single
  ``brave_web_search`` tool that hits the Brave Web Search API. The
  agent calls the tool once, synthesizes a short answer from the
  results, and returns text + the deduplicated source list captured
  during tool invocation.

Why Brave (and not Foundry / Bing Grounding)?
We need to keep all model traffic on the existing Azure OpenAI
deployment that lives behind APIM. The Foundry Agents API (which would
host Bing Grounding server-side) cannot be reached through APIM, so we
keep Bing-style "hosted tool" semantics on the client side: Brave is a
plain HTTP API we can call directly, register as an MAF ``ai_function``
tool, and let the existing AOAI chat client orchestrate.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any, Protocol, runtime_checkable

from azure.identity import DefaultAzureCredential

from momdiary.agents.brave_search import (
    BraveResult,
    BraveSearchClient,
    BraveSearchError,
)
from momdiary.agents.session_store import ChatTurn
from momdiary.config import Settings, get_settings
from momdiary.observability.logging import get_logger

logger = get_logger(__name__)


# Lazy MAF imports so unit-test environments without MAF installed can still
# exercise the `WebSearchPort` protocol via stubs.
try:  # pragma: no cover - import guard
    from agent_framework import Agent  # type: ignore[import-not-found,import-untyped]
    from agent_framework_azure_ai import (  # type: ignore[import-not-found,import-untyped]
        AzureOpenAIChatClient,
    )
except Exception:  # noqa: BLE001
    Agent = None  # type: ignore[assignment,misc]
    AzureOpenAIChatClient = None  # type: ignore[assignment,misc]


_RESEARCH_INSTRUCTIONS = """\
You are MomDiary's research assistant. Your role is to answer baby-care
questions using authoritative pediatric sources fetched through the
`brave_web_search` tool.

# Rules

1. ALWAYS call `brave_web_search` first with a focused query derived from
   the user's question. Never answer from memory and never call the tool
   more than once per turn.
2. Read the JSON list of results the tool returns and synthesize a
   concise answer (3-6 short paragraphs maximum) using ONLY what those
   results say. Prefer reputable pediatric sources (AAP, CDC, NHS,
   WHO, Mayo Clinic, Cleveland Clinic, KidsHealth, university hospitals).
3. End every answer with this exact disclaimer on its own line:
   "This is general information, not medical advice. Always consult your
   pediatrician for medical decisions about your baby."
4. If the user's question is not about baby care, reply with a short
   refusal beginning with "I can only help with baby-care research
   questions." and call no tools.
5. If the question asks for medical diagnosis, emergency triage, or
   anything that could harm a baby if mis-applied, reply with a short
   refusal beginning with "I can't help with that request." and call no
   tools.
6. Never reveal raw search results, tool IDs, or implementation details.
"""


@runtime_checkable
class WebSearchPort(Protocol):
    """Single-method port the runner depends on.

    Implementations must return a ``(synthesized_text, citations)`` tuple
    where each citation is a dict containing at minimum ``title`` and
    ``url``.

    ``history`` is the recent caregiver+assistant transcript (oldest
    first, excluding the current caregiver message) trimmed to the
    configured prompt token budget. Adapters are free to ignore it, but
    the production Brave adapter folds it into the user prompt so
    follow-up questions retain context.
    """

    async def search(
        self,
        query: str,
        *,
        age_label: str = "",
        history: list[ChatTurn] = ...,
    ) -> tuple[str, list[dict[str, str]]]: ...


class ResearchUnavailableError(RuntimeError):
    """Raised by ``WebSearchPort.search`` when the upstream is unreachable."""


# ---------------------------------------------------------------------------
# Brave-backed research adapter
# ---------------------------------------------------------------------------


def _build_brave_tool(
    brave: BraveSearchClient,
    captured: list[BraveResult],
    *,
    count: int,
) -> Any:
    """Construct a per-request MAF tool that proxies to Brave.

    The wrapper appends every result Brave returns to ``captured`` so the
    adapter can build the final citation list from the SAME data the LLM
    saw (no need to re-extract from response annotations). The wrapper
    returns a JSON string — MAF accepts any string return.
    """

    async def brave_web_search(query: str) -> str:
        """Search the web via Brave Search and return a JSON list of results.

        Each result has keys: title, url, description. Use the
        description to ground your answer and cite the URLs.
        """
        try:
            results = await brave.search(query, count=count)
        except BraveSearchError as exc:
            logger.warning(
                "research.brave.tool_error",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise ResearchUnavailableError(str(exc)) from exc

        captured.extend(results)
        return json.dumps([r.to_tool_payload() for r in results], ensure_ascii=False)

    # MAF derives the JSON schema from `__signature__` + `__annotations__`.
    brave_web_search.__name__ = "brave_web_search"
    brave_web_search.__qualname__ = "brave_web_search"
    brave_web_search.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        parameters=[
            inspect.Parameter(
                "query",
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=str,
            ),
        ],
        return_annotation=str,
    )
    brave_web_search.__annotations__ = {"query": str, "return": str}
    return brave_web_search


class BraveResearchAdapter:
    """Production ``WebSearchPort`` backed by Brave Search + AOAI synthesis.

    Construction is cheap. The Azure OpenAI chat client and the
    underlying Brave HTTP client are built lazily on the first
    ``search`` call.

    Raises :class:`ResearchUnavailableError` from ``search`` when:
      * MAF / ``agent-framework-azure-ai`` is not installed,
      * the Brave API key is not configured,
      * the Brave HTTP call fails with quota / 4xx / 5xx, or
      * the MAF agent run itself raises.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings: Settings = settings or get_settings()
        self._brave: BraveSearchClient | None = None
        self._chat_client: Any | None = None

    async def aclose(self) -> None:
        if self._brave is not None:
            await self._brave.aclose()
            self._brave = None

    # -- lazy builders -----------------------------------------------------

    def _ensure_brave(self) -> BraveSearchClient:
        if self._brave is not None:
            return self._brave
        api_key = self._settings.momdiary_research_brave_api_key
        if not api_key:
            raise ResearchUnavailableError(
                "MOMDIARY_RESEARCH_BRAVE_API_KEY is not configured."
            )
        self._brave = BraveSearchClient(
            api_key=api_key,
            endpoint=self._settings.momdiary_research_brave_endpoint,
            safesearch=self._settings.momdiary_research_brave_safesearch,
            country=self._settings.momdiary_research_brave_country,
            timeout_seconds=float(
                self._settings.momdiary_research_web_search_timeout_seconds
            ),
        )
        logger.info(
            "research.brave.client_built",
            endpoint=self._settings.momdiary_research_brave_endpoint,
            safesearch=self._settings.momdiary_research_brave_safesearch,
            country=self._settings.momdiary_research_brave_country,
        )
        return self._brave

    def _ensure_chat_client(self) -> Any:
        if self._chat_client is not None:
            return self._chat_client
        if AzureOpenAIChatClient is None or Agent is None:
            raise ResearchUnavailableError(
                "agent-framework / agent-framework-azure-ai is not installed."
            )
        if not self._settings.azure_openai_endpoint:
            raise ResearchUnavailableError(
                "AZURE_OPENAI_ENDPOINT is not configured."
            )
        if not self._settings.azure_openai_deployment:
            raise ResearchUnavailableError(
                "AZURE_OPENAI_DEPLOYMENT is not configured."
            )
        credential = DefaultAzureCredential()
        self._chat_client = AzureOpenAIChatClient(
            endpoint=self._settings.azure_openai_endpoint,
            deployment_name=self._settings.azure_openai_deployment,
            api_version=self._settings.azure_openai_api_version,
            credential=credential,
        )
        logger.info(
            "research.chat_client.built",
            endpoint=self._settings.azure_openai_endpoint,
            deployment=self._settings.azure_openai_deployment,
        )
        return self._chat_client

    # -- WebSearchPort -----------------------------------------------------

    async def search(
        self,
        query: str,
        *,
        age_label: str = "",
        history: list[ChatTurn] | None = None,
    ) -> tuple[str, list[dict[str, str]]]:
        """Run one Brave-grounded research turn.

        ``age_label`` is folded into the prompt prefix so the model can
        scope guidance to the baby's age band when known
        (e.g. "4-month-old"). Empty string disables the prefix.

        ``history`` is the recent transcript (oldest first, excluding
        the current caregiver message). When non-empty it is rendered
        as a short ``Previous conversation`` preamble so follow-up
        questions ("and for newborns?") retain context.
        """
        chat_client = self._ensure_chat_client()
        brave = self._ensure_brave()
        assert Agent is not None  # noqa: S101 — narrowed by _ensure_chat_client

        captured: list[BraveResult] = []
        tool = _build_brave_tool(
            brave,
            captured,
            count=self._settings.momdiary_research_brave_count,
        )
        agent = Agent(
            chat_client,
            _RESEARCH_INSTRUCTIONS,
            tools=[tool],
        )

        prefix = f"For a {age_label}: " if age_label else ""
        transcript = _render_history(history or [])
        full_query = f"{transcript}{prefix}{query}".strip()

        # Print the exact prompt the agent will see. This is the single
        # source of truth for "what did we send the LLM?" — useful when
        # the model's answer surprises us. `prompt_length` and
        # `history_turns` give a quick scan of how much context the model
        # received without parsing the full text field.
        logger.info(
            "research.agent.prompt",
            history_turns=len(history or []),
            age_label=age_label,
            prompt_length=len(full_query),
            prompt=full_query,
        )

        try:
            response = await agent.run(full_query)
        except ResearchUnavailableError:
            raise
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - boundary translation
            logger.warning(
                "research.agent.run_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise ResearchUnavailableError(str(exc)) from exc

        # Deduplicate by URL while preserving the order the model saw.
        seen: set[str] = set()
        citations: list[dict[str, str]] = []
        for r in captured:
            if r.url in seen:
                continue
            seen.add(r.url)
            citations.append(r.to_source())

        return (response.text or "", citations)


def _render_history(history: list[ChatTurn]) -> str:
    """Render prior turns as a short transcript preamble.

    Keeps the format compact (one line per turn) so it fits the model
    context cheaply and is easy for the LLM to follow. Empty history
    returns an empty string so single-turn calls keep their original
    prompt shape.
    """
    if not history:
        return ""
    lines: list[str] = ["Previous conversation:"]
    for turn in history:
        speaker = "Caregiver" if turn.role == "caregiver" else "Assistant"
        text = (turn.text or "").strip().replace("\n", " ")
        if not text:
            continue
        lines.append(f"{speaker}: {text}")
    lines.append("")  # blank line before the current question
    lines.append("Current question: ")
    return "\n".join(lines)


__all__ = [
    "BraveResearchAdapter",
    "ResearchUnavailableError",
    "WebSearchPort",
]
