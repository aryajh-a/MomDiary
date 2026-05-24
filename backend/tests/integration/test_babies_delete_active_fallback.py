"""Active-baby fallback on soft-delete — Feature 007 T038 / FR-017.

When a caregiver removes their currently-active baby, the server must
atomically reassign `active_baby_id` to the caregiver's most-recently-added
remaining baby (created_at DESC), or `NULL` if none remain. The reassignment
happens in the same flush as the soft-delete so the invariant
"active_baby_id is NULL or points at a live owned baby" never breaks.

These tests exercise the public HTTP surface (`DELETE /v1/babies/{id}` +
`GET /v1/auth/me`) and rely on the seeded caregiver fixture from conftest.py.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_delete_only_baby_clears_active(anon_client: AsyncClient) -> None:
    """Owner with a single baby: deleting it sets active_baby_id back to NULL."""
    await anon_client.post(
        "/v1/auth/register",
        json={
            "email": "solo@example.com",
            "password": "Pa55word!solo",
            "display_name": "Solo",
        },
    )
    only = await anon_client.post(
        "/v1/babies",
        json={"display_name": "Only", "date_of_birth": "2025-04-01"},
    )
    only_id = only.json()["id"]

    me = await anon_client.get("/v1/auth/me")
    assert me.json()["user"]["active_baby_id"] == only_id

    delete = await anon_client.delete(f"/v1/babies/{only_id}")
    assert delete.status_code in (200, 204), delete.text

    me = await anon_client.get("/v1/auth/me")
    assert me.json()["user"]["active_baby_id"] is None


@pytest.mark.asyncio
async def test_delete_active_falls_back_to_most_recent_other(
    anon_client: AsyncClient,
) -> None:
    """Three babies (oldest active): deleting the active baby promotes the
    most-recently-added remaining baby, not the oldest."""
    await anon_client.post(
        "/v1/auth/register",
        json={
            "email": "trio@example.com",
            "password": "Pa55word!trio",
            "display_name": "Trio",
        },
    )
    first = await anon_client.post(
        "/v1/babies",
        json={"display_name": "First", "date_of_birth": "2025-04-01"},
    )
    first_id = first.json()["id"]
    await anon_client.post(
        "/v1/babies",
        json={"display_name": "Middle", "date_of_birth": "2025-04-02"},
    )
    newest = await anon_client.post(
        "/v1/babies",
        json={"display_name": "Newest", "date_of_birth": "2025-04-03"},
    )
    newest_id = newest.json()["id"]

    # `first` was auto-activated when it was the very first baby.
    me = await anon_client.get("/v1/auth/me")
    assert me.json()["user"]["active_baby_id"] == first_id

    delete = await anon_client.delete(f"/v1/babies/{first_id}")
    assert delete.status_code in (200, 204), delete.text

    me = await anon_client.get("/v1/auth/me")
    # Most-recently-added remaining baby wins → "Newest", not "Middle".
    assert me.json()["user"]["active_baby_id"] == newest_id


@pytest.mark.asyncio
async def test_delete_non_active_does_not_change_active(
    anon_client: AsyncClient,
) -> None:
    """Deleting a non-active baby leaves active_baby_id alone."""
    await anon_client.post(
        "/v1/auth/register",
        json={
            "email": "pair@example.com",
            "password": "Pa55word!pair",
            "display_name": "Pair",
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
    second_id = second.json()["id"]

    me = await anon_client.get("/v1/auth/me")
    assert me.json()["user"]["active_baby_id"] == first_id

    delete = await anon_client.delete(f"/v1/babies/{second_id}")
    assert delete.status_code in (200, 204), delete.text

    me = await anon_client.get("/v1/auth/me")
    assert me.json()["user"]["active_baby_id"] == first_id
