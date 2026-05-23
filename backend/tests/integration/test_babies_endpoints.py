"""Integration tests for `/v1/babies` endpoints — feature 006 US2 / US5 (T037, T065)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_babies_happy_path(client: AsyncClient) -> None:
    r = await client.get("/v1/babies")
    assert r.status_code == 200
    items = r.json()["items"]
    # The seeded caregiver has exactly one baby.
    assert len(items) == 1
    assert items[0]["display_name"] == "Seed Baby"


@pytest.mark.asyncio
async def test_create_first_baby_auto_activates(
    anon_client: AsyncClient,
) -> None:
    # Register a fresh caregiver (no babies yet).
    reg = await anon_client.post(
        "/v1/auth/register",
        json={
            "email": "alice@example.com",
            "password": "Pa55word!alice",
            "display_name": "Alice",
        },
    )
    assert reg.status_code == 201
    assert reg.json()["user"]["active_baby_id"] is None

    create = await anon_client.post(
        "/v1/babies",
        json={"display_name": "Bobby", "date_of_birth": "2025-04-01"},
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["display_name"] == "Bobby"
    new_baby_id = body["id"]

    me = await anon_client.get("/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["active_baby_id"] == new_baby_id


@pytest.mark.asyncio
async def test_create_second_baby_does_not_change_active(
    anon_client: AsyncClient,
) -> None:
    await anon_client.post(
        "/v1/auth/register",
        json={
            "email": "ann@example.com",
            "password": "Pa55word!ann",
            "display_name": "Ann",
        },
    )
    first = await anon_client.post(
        "/v1/babies",
        json={"display_name": "First", "date_of_birth": "2025-04-01"},
    )
    first_id = first.json()["id"]
    second = await anon_client.post(
        "/v1/babies",
        json={"display_name": "Second", "date_of_birth": "2025-04-02"},
    )
    assert second.status_code == 201
    me = await anon_client.get("/v1/auth/me")
    assert me.json()["user"]["active_baby_id"] == first_id


@pytest.mark.asyncio
async def test_cross_tenant_get_returns_404(
    anon_client: AsyncClient, caregiver_factory
) -> None:
    # Two caregivers, each with one baby.
    carol = await caregiver_factory(email="carol@example.com", baby_name="Cara")
    dave = await caregiver_factory(email="dave@example.com", baby_name="Dax")

    # Sign in as Carol and try to PATCH Dave's baby.
    anon_client.cookies.set("momdiary_session", carol.session_token)
    r = await anon_client.patch(
        f"/v1/babies/{dave.baby_id}",
        json={"display_name": "Hacked"},
    )
    assert r.status_code == 404
    assert r.json()["error"] == "not_found"


@pytest.mark.asyncio
async def test_patch_baby_updates_display_name(client: AsyncClient, seed_caregiver) -> None:
    r = await client.patch(
        f"/v1/babies/{seed_caregiver.baby_id}",
        json={"display_name": "Renamed"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["display_name"] == "Renamed"


@pytest.mark.asyncio
async def test_delete_active_baby_clears_active(
    anon_client: AsyncClient,
) -> None:
    # New caregiver with two babies.
    await anon_client.post(
        "/v1/auth/register",
        json={
            "email": "frank@example.com",
            "password": "Pa55word!frank",
            "display_name": "Frank",
        },
    )
    a = await anon_client.post(
        "/v1/babies",
        json={"display_name": "BabyA", "date_of_birth": "2025-04-01"},
    )
    b = await anon_client.post(
        "/v1/babies",
        json={"display_name": "BabyB", "date_of_birth": "2025-04-02"},
    )
    a_id = a.json()["id"]
    b_id = b.json()["id"]

    # A is active (first-baby rule). Delete A → active_baby_id is cleared so
    # the caregiver must explicitly pick a remaining baby (FR-019b / svc behavior).
    r = await anon_client.delete(f"/v1/babies/{a_id}")
    assert r.status_code == 200

    me = await anon_client.get("/v1/auth/me")
    assert me.json()["user"]["active_baby_id"] is None

    # And listing no longer includes A.
    list_r = await anon_client.get("/v1/babies")
    ids = [item["id"] for item in list_r.json()["items"]]
    assert a_id not in ids
    assert b_id in ids


@pytest.mark.asyncio
async def test_delete_last_baby_clears_active(anon_client: AsyncClient) -> None:
    await anon_client.post(
        "/v1/auth/register",
        json={
            "email": "gina@example.com",
            "password": "Pa55word!gina",
            "display_name": "Gina",
        },
    )
    only = await anon_client.post(
        "/v1/babies",
        json={"display_name": "Only", "date_of_birth": "2025-04-01"},
    )
    only_id = only.json()["id"]

    r = await anon_client.delete(f"/v1/babies/{only_id}")
    assert r.status_code == 200
    me = await anon_client.get("/v1/auth/me")
    assert me.json()["user"]["active_baby_id"] is None
