"""T007 — Contract tests for `POST /v1/research`.

Implements the gates listed in
`specs/011-research-web-context/contracts/research-api.md#test-gates`.

These tests are **dependency-overrides only** — they do not require a real
Postgres database, JWT-signing infrastructure, or a live Brave API key.
Auth and the research runner are stubbed via FastAPI's
`app.dependency_overrides`, isolating the HTTP surface (request shape →
runner.run → response envelope mapping) from any I/O.

Outcome-by-outcome behavior of the runner itself is covered in
`tests/integration/test_research_e2e.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient


# Sentinel ids used across tests.
_USER_ID = 4242
_BABY_ID = 7
_SESSION_ID = "11111111-1111-4111-8111-111111111111"


# ---------------------------------------------------------------------------
# App + dependency-override scaffolding
# ---------------------------------------------------------------------------


def _build_test_app(*, runner_result: Any, runner_mock: AsyncMock) -> Any:
    """Build a fresh app and wire it up with deterministic dep overrides.

    Returns the configured FastAPI app. Tests own the lifecycle of the
    `AsyncClient` so they can inspect headers / body easily.
    """
    # Force the in-memory session store to avoid any Postgres lookup
    # during app construction.
    import os

    os.environ.setdefault("MOMDIARY_SESSION_STORE", "memory")
    os.environ.setdefault("MOMDIARY_APP_ENV", "test")
    # Brave API key is required at runtime by the adapter but the tests
    # override the runner entirely, so we don't need a real one.
    os.environ.setdefault("MOMDIARY_RESEARCH_BRAVE_API_KEY", "")

    from momdiary.api.dependencies import get_research_runner
    from momdiary.auth.dependencies import get_current_user, require_active_baby
    from momdiary.config import get_settings
    from momdiary.main import create_app
    from momdiary.models.orm import Baby, User

    get_settings.cache_clear()  # type: ignore[attr-defined]
    app = create_app()

    # Stub auth — bypass Clerk JWT verification entirely.
    fake_user = User(
        id=_USER_ID,
        clerk_user_id="user_test_42",
        email="seed@example.com",
        display_name="Test Caregiver",
        email_verified_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )

    fake_baby = Baby(
        id=_BABY_ID,
        owner_user_id=_USER_ID,
        display_name="Test Baby",
        date_of_birth="2025-06-01",
    )

    @dataclass(frozen=True, slots=True)
    class _CurrentUserStub:
        id: int
        user: User
        email_verified: bool = True

    async def _override_current_user() -> _CurrentUserStub:
        return _CurrentUserStub(id=_USER_ID, user=fake_user)

    async def _override_active_baby() -> Baby:
        return fake_baby

    async def _override_runner() -> Any:
        # The mock returns the configured runner_result.
        runner_mock.return_value = runner_result
        return type(
            "_StubRunner",
            (),
            {"run": runner_mock},
        )()

    app.dependency_overrides[get_current_user] = _override_current_user
    app.dependency_overrides[require_active_baby] = _override_active_baby
    app.dependency_overrides[get_research_runner] = _override_runner
    return app


def _make_run_result(
    *,
    outcome: str,
    agent_message: str,
    sources: list[dict[str, str]] | None = None,
    session_id: str = _SESSION_ID,
    correlation_id: str = "00000000-0000-4000-8000-000000000001",
) -> Any:
    """Build a `ResearchRunResult` instance via the production class."""
    from momdiary.agents.research_runner import ResearchRunResult

    return ResearchRunResult(
        outcome=outcome,  # type: ignore[arg-type]
        agent_message=agent_message,
        sources=sources or [],
        session_id=session_id,
        correlation_id=correlation_id,
    )


# ---------------------------------------------------------------------------
# Gate 1 — happy path
# ---------------------------------------------------------------------------


_DISCLAIMER_SUFFIX = (
    "This is general information, not medical advice. "
    "Always consult your pediatrician for medical decisions about your baby."
)


@pytest.mark.asyncio
async def test_happy_path_returns_research_answer_with_3_to_5_sources() -> None:
    """SC-008 / FR-008 — `research_answer` + 3-5 sources + disclaimer + headers."""
    cid = "00000000-0000-4000-8000-000000000001"
    sources = [
        {"title": "AAP", "url": "https://www.healthychildren.org/x"},
        {"title": "NHS", "url": "https://www.nhs.uk/y"},
        {"title": "CDC", "url": "https://www.cdc.gov/z"},
    ]
    result = _make_run_result(
        outcome="research_answer",
        agent_message=f"Most guidance suggests ... {_DISCLAIMER_SUFFIX}",
        sources=sources,
        correlation_id=cid,
    )
    runner_mock = AsyncMock()
    app = _build_test_app(runner_result=result, runner_mock=runner_mock)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.post(
            "/v1/research",
            json={"message": "How much night sleep should my baby get?"},
            headers={
                "Authorization": "Bearer fake-token",
                # Pin the correlation id so both the middleware (which
                # writes the X-Correlation-ID response header) and the
                # mocked runner (which fills the body's correlation_id)
                # agree.
                "X-Correlation-ID": cid,
            },
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["outcome"] == "research_answer"
    assert 3 <= len(body["sources"]) <= 5
    assert all({"title", "url"} <= set(s.keys()) for s in body["sources"])
    assert body["agent_message"].endswith(_DISCLAIMER_SUFFIX)
    assert body["correlation_id"] == cid
    assert body["session_id"] == _SESSION_ID
    assert r.headers["X-Session-ID"] == _SESSION_ID
    assert r.headers["X-Correlation-ID"] == cid


# ---------------------------------------------------------------------------
# Gate 2 — session preservation across turns
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_id_preserved_across_calls() -> None:
    """FR-007 — passing X-Session-ID forwards to runner and is echoed back."""
    result = _make_run_result(
        outcome="research_answer",
        agent_message=f"Answer. {_DISCLAIMER_SUFFIX}",
        sources=[
            {"title": "AAP", "url": "https://a.org/x"},
            {"title": "NHS", "url": "https://n.org/y"},
            {"title": "CDC", "url": "https://c.org/z"},
        ],
    )
    runner_mock = AsyncMock()
    app = _build_test_app(runner_result=result, runner_mock=runner_mock)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        await c.post(
            "/v1/research",
            json={"message": "first question"},
            headers={
                "Authorization": "Bearer fake-token",
                "X-Session-ID": _SESSION_ID,
            },
        )

    # Runner was invoked with session_id=_SESSION_ID — the api layer passes
    # it through verbatim and the runner is the only place that consults
    # the store. We assert via the mock call.
    call = runner_mock.call_args
    assert call is not None
    kwargs = call.kwargs
    assert kwargs.get("session_id") == _SESSION_ID


# ---------------------------------------------------------------------------
# Gate 3 — missing JWT → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_authorization_returns_401() -> None:
    """FR-018 + Clerk auth — no Bearer token → 401."""
    # Build app WITHOUT overriding `get_current_user` so the real Clerk
    # path runs and rejects the missing header.
    import os

    os.environ.setdefault("MOMDIARY_SESSION_STORE", "memory")
    os.environ.setdefault("MOMDIARY_APP_ENV", "test")

    from momdiary.config import get_settings
    from momdiary.main import create_app

    get_settings.cache_clear()  # type: ignore[attr-defined]
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.post("/v1/research", json={"message": "hi"})

    assert r.status_code == 401, r.text
    body = r.json()
    # Envelope per `auth.dependencies._error`.
    assert body.get("error") == "not_signed_in"


# ---------------------------------------------------------------------------
# Gate 4 — empty message → 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_message_returns_400() -> None:
    """Pydantic `min_length=1` enforces the empty-message rejection."""
    result = _make_run_result(
        outcome="research_answer",
        agent_message="never called",
        sources=[],
    )
    runner_mock = AsyncMock()
    app = _build_test_app(runner_result=result, runner_mock=runner_mock)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.post(
            "/v1/research",
            json={"message": ""},
            headers={"Authorization": "Bearer fake-token"},
        )

    assert r.status_code == 422 or r.status_code == 400, r.text
    # Runner must never be called for invalid input.
    runner_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Gate 5 — mocked timeout → research_unavailable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_returns_research_unavailable_with_empty_sources() -> None:
    """FR-014 — runner mapping `research_unavailable` exits the API as 200 + outcome."""
    result = _make_run_result(
        outcome="research_unavailable",
        agent_message=(
            "Research is temporarily unavailable. Please try again in a moment."
        ),
        sources=[],
    )
    runner_mock = AsyncMock()
    app = _build_test_app(runner_result=result, runner_mock=runner_mock)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.post(
            "/v1/research",
            json={"message": "anything"},
            headers={"Authorization": "Bearer fake-token"},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["outcome"] == "research_unavailable"
    assert body["sources"] == []
    assert "temporarily unavailable" in body["agent_message"]


# ---------------------------------------------------------------------------
# Gate 6 — refused outcomes carry empty sources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "expected_msg_fragment"),
    [
        ("scope_refused", "baby-care research"),
        ("safety_refused", "I can't help with that request"),
        ("no_sources_found", "couldn't find a reliable source"),
    ],
)
async def test_refused_outcomes_have_empty_sources_and_fixed_copy(
    outcome: str, expected_msg_fragment: str
) -> None:
    """FR-013 / SC-007 — non-answer outcomes always have `sources=[]`."""
    canned_msg = {
        "scope_refused": (
            "I can only help with baby-care research questions. "
            "Please rephrase as a question about your baby's care."
        ),
        "safety_refused": (
            "I can't help with that request. If you have concerns about "
            "your baby's safety, please contact your pediatrician or an "
            "emergency line."
        ),
        "no_sources_found": (
            "I couldn't find a reliable source for this. Try rephrasing, "
            "or consult your pediatrician."
        ),
    }[outcome]
    result = _make_run_result(
        outcome=outcome, agent_message=canned_msg, sources=[]
    )
    runner_mock = AsyncMock()
    app = _build_test_app(runner_result=result, runner_mock=runner_mock)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.post(
            "/v1/research",
            json={"message": "anything"},
            headers={"Authorization": "Bearer fake-token"},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["outcome"] == outcome
    assert body["sources"] == []
    assert expected_msg_fragment in body["agent_message"]
