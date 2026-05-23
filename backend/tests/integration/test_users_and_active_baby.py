"""Integration tests for users + active-baby — feature 006 US4 (T058, T064)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_patch_users_me_updates_display_name(client: AsyncClient) -> None:
    r = await client.patch(
        "/v1/users/me",
        json={"display_name": "Updated Name"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["user"]["display_name"] == "Updated Name"


@pytest.mark.asyncio
async def test_set_active_baby_to_owned_baby(anon_client: AsyncClient) -> None:
    await anon_client.post(
        "/v1/auth/register",
        json={
            "email": "hank@example.com",
            "password": "Pa55word!hank",
            "display_name": "Hank",
        },
    )
    a = await anon_client.post(
        "/v1/babies",
        json={"display_name": "First", "date_of_birth": "2025-04-01"},
    )
    b = await anon_client.post(
        "/v1/babies",
        json={"display_name": "Second", "date_of_birth": "2025-04-02"},
    )
    b_id = b.json()["id"]

    r = await anon_client.post(
        "/v1/users/me/active-baby", json={"baby_id": b_id}
    )
    assert r.status_code == 200, r.text
    me = await anon_client.get("/v1/auth/me")
    assert me.json()["user"]["active_baby_id"] == b_id


@pytest.mark.asyncio
async def test_set_active_baby_for_other_caregivers_baby_returns_404(
    anon_client: AsyncClient, caregiver_factory
) -> None:
    ivan = await caregiver_factory(email="ivan@switch.com", baby_name="Iggy")
    jane = await caregiver_factory(email="jane@switch.com", baby_name="Jam")

    anon_client.cookies.set("momdiary_session", ivan.session_token)
    r = await anon_client.post(
        "/v1/users/me/active-baby", json={"baby_id": jane.baby_id}
    )
    assert r.status_code == 404
    assert r.json()["error"] == "not_found"


@pytest.mark.asyncio
async def test_session_restore_preserves_active_baby(
    anon_client: AsyncClient,
) -> None:
    reg = await anon_client.post(
        "/v1/auth/register",
        json={
            "email": "kim@restore.com",
            "password": "Pa55word!kim",
            "display_name": "Kim",
        },
    )
    assert reg.status_code == 201
    a = await anon_client.post(
        "/v1/babies",
        json={"display_name": "Alpha", "date_of_birth": "2025-04-01"},
    )
    b = await anon_client.post(
        "/v1/babies",
        json={"display_name": "Bravo", "date_of_birth": "2025-04-02"},
    )
    b_id = b.json()["id"]
    await anon_client.post(
        "/v1/users/me/active-baby", json={"baby_id": b_id}
    )

    # Capture the cookie + simulate a new "tab" by clearing in-memory state
    # but reusing the same session token.
    token = anon_client.cookies.get("momdiary_session")
    anon_client.cookies.clear()
    anon_client.cookies.set("momdiary_session", token)

    me = await anon_client.get("/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["active_baby_id"] == b_id
