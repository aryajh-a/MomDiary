"""Integration tests for the Baby Profile feature (010).

Self-contained: these tests do NOT use the legacy password/session fixtures
in conftest (which predate the Clerk migration). They reuse the working
`configured_app` fixture (ephemeral Postgres schema + migrations), seed
caregivers + babies directly through the session factory, and authenticate by
overriding the Clerk `get_current_user` dependency.

Covers: extended `GET /v1/babies` projection, extended `PATCH /v1/babies/{id}`
(happy path, enum/range validation, clear-to-null, active-baby-unchanged,
round-trip losslessness) and cross-tenant isolation.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from momdiary.auth.clerk import ClerkClaims
from momdiary.auth.dependencies import CurrentUser, get_current_user
from momdiary.db.engine import get_session_factory
from momdiary.models.orm import Baby, GrowthMeasurement, User


def _today_default_tz() -> str:
    """Today's date in the test default zone (matches the service's clock)."""
    return datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@pytest_asyncio.fixture
async def seed(configured_app: Any) -> SimpleNamespace:
    """Two verified caregivers; the first owns a baby, the second owns another."""
    factory = get_session_factory()
    async with factory() as s:
        owner = User(
            clerk_user_id="clerk_owner",
            email="owner@example.com",
            display_name="Owner",
            email_verified_at=_iso(),
        )
        s.add(owner)
        await s.flush()
        baby = Baby(
            owner_user_id=owner.id,
            display_name="Mia Johnson",
            date_of_birth="2025-01-20",
        )
        s.add(baby)
        await s.flush()
        owner.active_baby_id = baby.id

        other = User(
            clerk_user_id="clerk_other",
            email="other@example.com",
            display_name="Other",
            email_verified_at=_iso(),
        )
        s.add(other)
        await s.flush()
        other_baby = Baby(
            owner_user_id=other.id,
            display_name="Bob",
            date_of_birth="2025-02-01",
        )
        s.add(other_baby)
        await s.flush()
        other.active_baby_id = other_baby.id
        await s.commit()

        return SimpleNamespace(
            owner_id=owner.id,
            baby_id=baby.id,
            active_baby_id=baby.id,
            other_id=other.id,
            other_baby_id=other_baby.id,
        )


def _auth_override(user_id: int):
    async def _override() -> CurrentUser:
        # Detached stand-in: the routes only read `auth.user.id`. Claims carry a
        # verified email so `require_verified_email` admits the write.
        user = User(id=user_id, clerk_user_id=f"clerk_{user_id}", email="x@x", display_name="x")
        claims = ClerkClaims(
            sub=f"clerk_{user_id}",
            email="x@x",
            email_verified=True,
            sid=None,
            iss="test",
            exp=0,
            iat=0,
        )
        return CurrentUser(user=user, claims=claims)

    return _override


@pytest_asyncio.fixture
async def client_as(configured_app: Any):
    """Factory: yields an AsyncClient authenticated as the given user id."""

    async def _make(user_id: int) -> AsyncClient:
        configured_app.dependency_overrides[get_current_user] = _auth_override(user_id)
        return AsyncClient(
            transport=ASGITransport(app=configured_app),
            base_url="http://test",
        )

    yield _make
    configured_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# US1 — extended projection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_babies_includes_new_fields_null_when_unset(
    seed: SimpleNamespace, client_as
) -> None:
    async with await client_as(seed.owner_id) as c:
        r = await c.get("/v1/babies")
    assert r.status_code == 200, r.text
    item = r.json()["items"][0]
    for field in ("gender", "weight_kg", "height_cm"):
        assert field in item
        assert item[field] is None


@pytest.mark.asyncio
async def test_existing_style_row_survives_with_null_profile_fields(
    seed: SimpleNamespace, client_as
) -> None:
    """A baby created without the 010 columns reads back with them as NULL
    (additive-nullable migration; existing rows stay valid — T003 spirit)."""
    async with await client_as(seed.owner_id) as c:
        r = await c.get("/v1/babies")
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["display_name"] == "Mia Johnson"
    assert item["weight_kg"] is None


# ---------------------------------------------------------------------------
# US2 — extended PATCH
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_sets_all_new_fields(seed: SimpleNamespace, client_as) -> None:
    async with await client_as(seed.owner_id) as c:
        r = await c.patch(
            f"/v1/babies/{seed.baby_id}",
            json={
                "gender": "girl",
                "weight_kg": 7.2,
                "height_cm": 62.0,
            },
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["gender"] == "girl"
    assert body["weight_kg"] == 7.2
    assert body["height_cm"] == 62.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"date_of_birth": "2999-01-01"},  # future
        {"gender": "male"},  # bad enum
        {"weight_kg": 0},  # non-positive
        {"weight_kg": 999},  # out of range
        {"height_cm": -1},  # non-positive
        {"height_cm": 5000},  # out of range
    ],
)
async def test_patch_rejects_invalid_input(
    seed: SimpleNamespace, client_as, payload: dict
) -> None:
    async with await client_as(seed.owner_id) as c:
        r = await c.patch(f"/v1/babies/{seed.baby_id}", json=payload)
        assert r.status_code == 422, r.text
        # Nothing persisted.
        after = await c.get("/v1/babies")
    item = after.json()["items"][0]
    assert item["gender"] is None
    assert item["weight_kg"] is None
    assert item["height_cm"] is None


@pytest.mark.asyncio
async def test_patch_explicit_null_clears_field(
    seed: SimpleNamespace, client_as
) -> None:
    async with await client_as(seed.owner_id) as c:
        set_r = await c.patch(
            f"/v1/babies/{seed.baby_id}", json={"gender": "girl"}
        )
        assert set_r.json()["gender"] == "girl"
        clear_r = await c.patch(
            f"/v1/babies/{seed.baby_id}", json={"gender": None}
        )
    assert clear_r.status_code == 200, clear_r.text
    assert clear_r.json()["gender"] is None


@pytest.mark.asyncio
async def test_weight_height_survive_round_trip(
    seed: SimpleNamespace, client_as
) -> None:
    """SC-005: a metric value survives save → re-read unchanged."""
    async with await client_as(seed.owner_id) as c:
        await c.patch(
            f"/v1/babies/{seed.baby_id}",
            json={"weight_kg": 6.35, "height_cm": 59.5},
        )
        again = await c.get("/v1/babies")
    item = again.json()["items"][0]
    assert item["weight_kg"] == 6.35
    assert item["height_cm"] == 59.5


@pytest.mark.asyncio
async def test_patch_does_not_change_active_baby(
    seed: SimpleNamespace, client_as
) -> None:
    """FR-016: editing a baby never changes the owner's active baby."""
    async with await client_as(seed.owner_id) as c:
        await c.patch(f"/v1/babies/{seed.baby_id}", json={"gender": "boy"})
    factory = get_session_factory()
    async with factory() as s:
        user = (
            await s.execute(select(User).where(User.id == seed.owner_id))
        ).scalar_one()
        assert user.active_baby_id == seed.active_baby_id


# ---------------------------------------------------------------------------
# Growth history (feature 010 — measurements + delta)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weight_edit_logs_measurement_and_last_measured(
    seed: SimpleNamespace, client_as
) -> None:
    async with await client_as(seed.owner_id) as c:
        r = await c.patch(
            f"/v1/babies/{seed.baby_id}",
            json={"weight_kg": 7.2, "height_cm": 62.0},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["last_measured_at"] == _today_default_tz()
    # First measurement → no prior to diff against.
    assert body["weight_kg_delta"] is None
    assert body["height_cm_delta"] is None
    # Exactly one measurement row was created.
    factory = get_session_factory()
    async with factory() as s:
        count = await s.scalar(
            select(func.count())
            .select_from(GrowthMeasurement)
            .where(GrowthMeasurement.baby_id == seed.baby_id)
        )
    assert count == 1


@pytest.mark.asyncio
async def test_delta_reflects_change_vs_previous_measurement(
    seed: SimpleNamespace, client_as
) -> None:
    # Seed a prior measurement on an earlier date.
    factory = get_session_factory()
    async with factory() as s:
        s.add(
            GrowthMeasurement(
                baby_id=seed.baby_id,
                weight_kg=6.9,
                height_cm=60.5,
                measured_at="2025-05-01",
                created_at="2025-05-01T00:00:00+00:00",
                updated_at="2025-05-01T00:00:00+00:00",
            )
        )
        await s.commit()

    async with await client_as(seed.owner_id) as c:
        r = await c.patch(
            f"/v1/babies/{seed.baby_id}",
            json={"weight_kg": 7.2, "height_cm": 62.0},
        )
    body = r.json()
    assert body["last_measured_at"] == _today_default_tz()
    assert body["weight_kg_delta"] == 0.3  # 7.2 - 6.9
    assert body["height_cm_delta"] == 1.5  # 62.0 - 60.5


@pytest.mark.asyncio
async def test_gender_only_edit_does_not_log_measurement(
    seed: SimpleNamespace, client_as
) -> None:
    async with await client_as(seed.owner_id) as c:
        r = await c.patch(f"/v1/babies/{seed.baby_id}", json={"gender": "girl"})
    assert r.status_code == 200
    assert r.json()["last_measured_at"] is None
    factory = get_session_factory()
    async with factory() as s:
        count = await s.scalar(
            select(func.count())
            .select_from(GrowthMeasurement)
            .where(GrowthMeasurement.baby_id == seed.baby_id)
        )
    assert count == 0


@pytest.mark.asyncio
async def test_same_day_edits_upsert_one_measurement(
    seed: SimpleNamespace, client_as
) -> None:
    async with await client_as(seed.owner_id) as c:
        await c.patch(f"/v1/babies/{seed.baby_id}", json={"weight_kg": 7.0})
        r = await c.patch(f"/v1/babies/{seed.baby_id}", json={"weight_kg": 7.4})
    assert r.json()["weight_kg"] == 7.4
    factory = get_session_factory()
    async with factory() as s:
        count = await s.scalar(
            select(func.count())
            .select_from(GrowthMeasurement)
            .where(GrowthMeasurement.baby_id == seed.baby_id)
        )
    # Two same-day saves collapse into a single upserted row.
    assert count == 1


# ---------------------------------------------------------------------------
# Cross-tenant isolation (FR-005 / SC-003)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_tenant_patch_returns_404_and_mutates_nothing(
    seed: SimpleNamespace, client_as
) -> None:
    async with await client_as(seed.other_id) as c:
        r = await c.patch(
            f"/v1/babies/{seed.baby_id}",  # owner's baby, not other's
            json={"gender": "girl"},
        )
    assert r.status_code == 404
    assert r.json()["error"] == "not_found"
    # The owner's baby is untouched.
    factory = get_session_factory()
    async with factory() as s:
        baby = (
            await s.execute(select(Baby).where(Baby.id == seed.baby_id))
        ).scalar_one()
        assert baby.gender is None
