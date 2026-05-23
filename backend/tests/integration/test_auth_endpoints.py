"""Integration tests for `/v1/auth/*` endpoints — feature 006 US1 (T028)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_then_me_returns_user(anon_client: AsyncClient) -> None:
    r = await anon_client.post(
        "/v1/auth/register",
        json={
            "email": "alice@example.com",
            "password": "Pa55word!alice",
            "display_name": "Alice",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["email"] == "alice@example.com"
    assert body["user"]["active_baby_id"] is None

    # Session cookie was set.
    assert "momdiary_session" in anon_client.cookies

    me = await anon_client.get("/v1/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["user"]["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_conflict(
    anon_client: AsyncClient,
) -> None:
    payload = {
        "email": "bob@example.com",
        "password": "Pa55word!bob",
        "display_name": "Bob",
    }
    r1 = await anon_client.post("/v1/auth/register", json=payload)
    assert r1.status_code == 201
    # Drop cookie so the duplicate request looks like a new registration.
    anon_client.cookies.clear()
    r2 = await anon_client.post("/v1/auth/register", json=payload)
    assert r2.status_code == 409
    body = r2.json()
    assert body["error"] == "conflict"
    assert "correlation_id" in body


@pytest.mark.asyncio
async def test_register_weak_password_returns_400(anon_client: AsyncClient) -> None:
    r = await anon_client.post(
        "/v1/auth/register",
        json={
            "email": "carol@example.com",
            "password": "short",
            "display_name": "Carol",
        },
    )
    assert r.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_login_happy_path(anon_client: AsyncClient) -> None:
    await anon_client.post(
        "/v1/auth/register",
        json={
            "email": "dan@example.com",
            "password": "Pa55word!dan",
            "display_name": "Dan",
        },
    )
    anon_client.cookies.clear()

    r = await anon_client.post(
        "/v1/auth/login",
        json={"email": "dan@example.com", "password": "Pa55word!dan"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["user"]["email"] == "dan@example.com"
    assert "momdiary_session" in anon_client.cookies


@pytest.mark.asyncio
async def test_login_wrong_password_returns_uniform_401(
    anon_client: AsyncClient,
) -> None:
    await anon_client.post(
        "/v1/auth/register",
        json={
            "email": "eve@example.com",
            "password": "Pa55word!eve",
            "display_name": "Eve",
        },
    )
    anon_client.cookies.clear()

    r = await anon_client.post(
        "/v1/auth/login",
        json={"email": "eve@example.com", "password": "wrongpassword!!"},
    )
    assert r.status_code == 401
    assert r.json()["error"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_login_unknown_email_returns_same_401_envelope(
    anon_client: AsyncClient,
) -> None:
    r = await anon_client.post(
        "/v1/auth/login",
        json={"email": "ghost@example.com", "password": "Pa55word!ghost"},
    )
    assert r.status_code == 401
    body = r.json()
    assert body["error"] == "invalid_credentials"
    # Uniform message — must NOT leak whether the account exists (FR-006).
    assert "Invalid" in body["message"]


@pytest.mark.asyncio
async def test_logout_then_me_returns_401(anon_client: AsyncClient) -> None:
    await anon_client.post(
        "/v1/auth/register",
        json={
            "email": "fay@example.com",
            "password": "Pa55word!fay",
            "display_name": "Fay",
        },
    )
    r = await anon_client.post("/v1/auth/logout")
    assert r.status_code == 200
    me = await anon_client.get("/v1/auth/me")
    assert me.status_code == 401
    assert me.json()["error"] == "unauthenticated"


@pytest.mark.asyncio
async def test_me_anonymous_returns_401(anon_client: AsyncClient) -> None:
    r = await anon_client.get("/v1/auth/me")
    assert r.status_code == 401
    assert r.json()["error"] == "unauthenticated"
