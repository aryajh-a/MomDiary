"""Unit tests for ``BraveSearchClient`` (no network).

The client is exercised through a mocked ``httpx.MockTransport`` so the
tests are fast, deterministic, and require no API key.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from momdiary.agents.brave_search import (
    BraveResult,
    BraveSearchClient,
    BraveSearchError,
)


def _make_transport(handler: Any) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def _ok_payload() -> dict:
    return {
        "web": {
            "results": [
                {
                    "title": "Safe sleep for babies - AAP",
                    "url": "https://www.aap.org/safe-sleep",
                    "description": "AAP recommends back-sleeping on a firm flat surface.",
                },
                {
                    "title": "Infant sleep - CDC",
                    "url": "https://www.cdc.gov/infant-sleep",
                    "description": "CDC guidance on safe-sleep environments.",
                },
            ]
        }
    }


@pytest.mark.asyncio
async def test_search_returns_parsed_results() -> None:
    captured_request: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured_request["params"] = dict(req.url.params)
        captured_request["headers"] = dict(req.headers)
        return httpx.Response(200, json=_ok_payload())

    async with BraveSearchClient(
        api_key="test-key", transport=_make_transport(handler)
    ) as client:
        results = await client.search("safe sleep newborn", count=5)

    assert len(results) == 2
    assert isinstance(results[0], BraveResult)
    assert results[0].url == "https://www.aap.org/safe-sleep"
    assert results[0].title.startswith("Safe sleep")
    assert results[0].to_source() == {
        "title": results[0].title,
        "url": results[0].url,
    }
    assert "title" in results[0].to_tool_payload()
    assert "description" in results[0].to_tool_payload()

    # The API key is sent through the documented header.
    assert captured_request["headers"]["x-subscription-token"] == "test-key"
    # Default safesearch + country are forwarded.
    assert captured_request["params"]["safesearch"] == "strict"
    assert captured_request["params"]["country"] == "US"
    # `count=5` is forwarded as a string by httpx.
    assert captured_request["params"]["count"] == "5"


@pytest.mark.asyncio
async def test_count_is_clamped_to_brave_limits() -> None:
    seen: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["count"] = req.url.params.get("count")
        return httpx.Response(200, json={"web": {"results": []}})

    async with BraveSearchClient(
        api_key="k", transport=_make_transport(handler)
    ) as client:
        await client.search("q", count=999)

    # 20 is the documented per-page maximum.
    assert seen["count"] == "20"


@pytest.mark.asyncio
async def test_quota_exhausted_raises() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Too Many Requests")

    async with BraveSearchClient(
        api_key="k", transport=_make_transport(handler)
    ) as client:
        with pytest.raises(BraveSearchError, match="quota"):
            await client.search("anything")


@pytest.mark.asyncio
async def test_unauthorized_raises() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad key")

    async with BraveSearchClient(
        api_key="bad", transport=_make_transport(handler)
    ) as client:
        with pytest.raises(BraveSearchError, match="401"):
            await client.search("anything")


@pytest.mark.asyncio
async def test_server_error_raises() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream down")

    async with BraveSearchClient(
        api_key="k", transport=_make_transport(handler)
    ) as client:
        with pytest.raises(BraveSearchError, match="upstream"):
            await client.search("anything")


@pytest.mark.asyncio
async def test_malformed_json_raises() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json at all")

    async with BraveSearchClient(
        api_key="k", transport=_make_transport(handler)
    ) as client:
        with pytest.raises(BraveSearchError, match="non-JSON"):
            await client.search("anything")


@pytest.mark.asyncio
async def test_missing_web_key_returns_empty_list() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    async with BraveSearchClient(
        api_key="k", transport=_make_transport(handler)
    ) as client:
        out = await client.search("anything")

    assert out == []


@pytest.mark.asyncio
async def test_skips_results_missing_url_or_title() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {"title": "", "url": "https://e.com"},
                        {"title": "Has no url", "url": ""},
                        {
                            "title": "Good",
                            "url": "https://good.example",
                            "description": "ok",
                        },
                    ]
                }
            },
        )

    async with BraveSearchClient(
        api_key="k", transport=_make_transport(handler)
    ) as client:
        results = await client.search("anything")

    assert [r.url for r in results] == ["https://good.example"]


@pytest.mark.asyncio
async def test_empty_query_rejected() -> None:
    client = BraveSearchClient(api_key="k")
    with pytest.raises(BraveSearchError, match="empty"):
        await client.search("   ")
    await client.aclose()


def test_constructor_requires_api_key() -> None:
    with pytest.raises(BraveSearchError, match="not configured"):
        BraveSearchClient(api_key="")


# Ensure JSON-serializable payload survives a round-trip — used inside the
# MAF tool wrapper to hand results to the LLM.
def test_to_tool_payload_is_json_safe() -> None:
    r = BraveResult(title="t", url="https://x", description="d")
    json.dumps([r.to_tool_payload()])
