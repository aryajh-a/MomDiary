"""Thin async HTTP client for the Brave Search Web API.

This module owns ONLY the HTTP boundary — it does not synthesize answers,
build agents, or apply policy. The MAF research agent in
:mod:`momdiary.agents.research_agent` consumes it through the
``BraveSearchClient.search`` coroutine.

Endpoint: ``GET https://api.search.brave.com/res/v1/web/search``
Auth:     header ``X-Subscription-Token: <api_key>``
Docs:     https://api-dashboard.search.brave.com/app/documentation/web-search/get-started
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from momdiary.observability.logging import get_logger

logger = get_logger(__name__)


class BraveSearchError(RuntimeError):
    """Raised on HTTP errors, quota exhaustion, or malformed responses."""


@dataclass(slots=True)
class BraveResult:
    """One web result returned by Brave Search.

    Only the fields we surface to the LLM and the response envelope are
    kept; everything else from the upstream payload is dropped.
    """

    title: str
    url: str
    description: str

    def to_source(self) -> dict[str, str]:
        """Return the ``{title, url}`` shape used by the response envelope."""
        return {"title": self.title, "url": self.url}

    def to_tool_payload(self) -> dict[str, str]:
        """Return the ``{title, url, description}`` shape passed to the LLM."""
        return {
            "title": self.title,
            "url": self.url,
            "description": self.description,
        }


class BraveSearchClient:
    """Async Brave Web Search client.

    Construction is cheap. The underlying ``httpx.AsyncClient`` is built
    lazily on the first ``search`` call and reused for subsequent calls.
    Call :meth:`aclose` (or use as an async context manager) to release
    the connection pool.
    """

    def __init__(
        self,
        api_key: str,
        *,
        endpoint: str = "https://api.search.brave.com/res/v1/web/search",
        safesearch: str = "strict",
        country: str = "US",
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise BraveSearchError("Brave API key is not configured.")
        self._api_key = api_key
        self._endpoint = endpoint
        self._safesearch = safesearch
        self._country = country
        self._timeout = httpx.Timeout(timeout_seconds)
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "BraveSearchClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": self._api_key,
                },
            )
        return self._client

    async def search(self, query: str, *, count: int = 8) -> list[BraveResult]:
        """Issue one Brave web-search request and return parsed results.

        Raises :class:`BraveSearchError` on HTTP errors (4xx/5xx) and on
        responses that lack a ``web.results`` array.
        """
        if not query or not query.strip():
            raise BraveSearchError("Brave search query must not be empty.")
        client = self._ensure_client()
        params: dict[str, str | int] = {
            "q": query,
            "count": max(1, min(count, 20)),
            "safesearch": self._safesearch,
            "country": self._country,
        }
        try:
            resp = await client.get(self._endpoint, params=params)
        except httpx.HTTPError as exc:
            raise BraveSearchError(f"Brave HTTP error: {exc}") from exc

        if resp.status_code == 401:
            raise BraveSearchError("Brave API key rejected (401).")
        if resp.status_code == 429:
            raise BraveSearchError("Brave quota exhausted (429).")
        if resp.status_code >= 500:
            raise BraveSearchError(f"Brave upstream error ({resp.status_code}).")
        if resp.status_code >= 400:
            raise BraveSearchError(
                f"Brave request rejected ({resp.status_code}): {resp.text[:200]}"
            )

        try:
            payload = resp.json()
        except ValueError as exc:
            raise BraveSearchError("Brave returned non-JSON body.") from exc

        raw_results = (
            (payload.get("web") or {}).get("results") or []
            if isinstance(payload, dict)
            else []
        )
        if not isinstance(raw_results, list):
            raise BraveSearchError("Brave returned an unexpected payload shape.")

        out: list[BraveResult] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = (item.get("url") or "").strip()
            title = (item.get("title") or "").strip()
            description = (item.get("description") or "").strip()
            if not url or not title:
                continue
            out.append(BraveResult(title=title, url=url, description=description))
        return out


__all__ = ["BraveResult", "BraveSearchClient", "BraveSearchError"]
