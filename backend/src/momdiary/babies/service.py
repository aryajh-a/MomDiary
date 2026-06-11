"""Baby CRUD service — feature 006.

All queries are scoped to `owner_user_id`. Soft-delete sets `deleted_at` and
clears the owner's `active_baby_id` if it pointed at the deleted baby.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.models.orm import Baby, GrowthMeasurement, User
from momdiary.schemas.babies import BabyCreate, BabyUpdate
from momdiary.services.time_service import get_request_timezone, now_in_tz


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True, slots=True)
class GrowthSummary:
    """Latest measurement date + change vs the previous measurement (FR-010 v2)."""

    last_measured_at: str | None = None
    weight_kg_delta: float | None = None
    height_cm_delta: float | None = None


class BabyConflictError(Exception):
    """Raised on owner-scoped business-rule violations (e.g., duplicate name)."""


class BabyService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_for_user(self, user_id: int) -> list[Baby]:
        stmt = (
            select(Baby)
            .where(Baby.owner_user_id == user_id, Baby.deleted_at.is_(None))
            .order_by(Baby.created_at.asc())
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def get_owned(self, user_id: int, baby_id: int) -> Baby | None:
        """None on miss OR cross-tenant (caller returns 404 either way)."""
        stmt = select(Baby).where(
            Baby.id == baby_id,
            Baby.owner_user_id == user_id,
            Baby.deleted_at.is_(None),
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def create(self, *, owner_user_id: int, payload: BabyCreate) -> Baby:
        now = _utcnow_iso()
        baby = Baby(
            owner_user_id=owner_user_id,
            display_name=payload.display_name,
            date_of_birth=payload.date_of_birth.isoformat(),
            color_tag=payload.color_tag,
            created_at=now,
            updated_at=now,
        )
        self._db.add(baby)
        await self._db.flush()
        return baby

    async def update(self, baby: Baby, payload: BabyUpdate) -> Baby:
        changed = False
        if payload.display_name is not None and payload.display_name != baby.display_name:
            baby.display_name = payload.display_name
            changed = True
        if payload.date_of_birth is not None:
            iso = payload.date_of_birth.isoformat()
            if iso != baby.date_of_birth:
                baby.date_of_birth = iso
                changed = True
        if payload.color_tag is not None and payload.color_tag != baby.color_tag:
            baby.color_tag = payload.color_tag
            changed = True
        # Feature 010 — clearable optional attributes. Only touch a field the
        # caller actually sent (model_fields_set), so an omitted field is left
        # alone while an explicit `null` clears it back to unset (FR-014).
        sent = payload.model_fields_set
        measurement_changed = False
        for attr in ("gender", "weight_kg", "height_cm"):
            if attr in sent:
                new_value = getattr(payload, attr)
                if new_value != getattr(baby, attr):
                    setattr(baby, attr, new_value)
                    changed = True
                    if attr in ("weight_kg", "height_cm"):
                        measurement_changed = True
        if changed:
            baby.updated_at = _utcnow_iso()
            await self._db.flush()
        # Growth history (feature 010): a weight/height edit logs/updates today's
        # measurement, snapshotting the baby's *current* values. Upsert-by-day so
        # repeated saves on the same date don't spam rows. Skipped when both
        # current values are unset (nothing meaningful to record).
        if measurement_changed and (
            baby.weight_kg is not None or baby.height_cm is not None
        ):
            await self._log_measurement(baby)
        return baby

    async def _log_measurement(self, baby: Baby) -> None:
        tz = await get_request_timezone(self._db)
        today = now_in_tz(tz).date().isoformat()
        existing = (
            await self._db.execute(
                select(GrowthMeasurement).where(
                    GrowthMeasurement.baby_id == baby.id,
                    GrowthMeasurement.measured_at == today,
                    GrowthMeasurement.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        now = _utcnow_iso()
        if existing is not None:
            existing.weight_kg = baby.weight_kg
            existing.height_cm = baby.height_cm
            existing.updated_at = now
        else:
            self._db.add(
                GrowthMeasurement(
                    baby_id=baby.id,
                    weight_kg=baby.weight_kg,
                    height_cm=baby.height_cm,
                    measured_at=today,
                    created_at=now,
                    updated_at=now,
                )
            )
        await self._db.flush()

    async def growth_summary(self, baby_id: int) -> GrowthSummary:
        """Latest measurement date + per-metric delta vs the previous one.

        Deltas are computed only when both the latest and the previous
        measurement carry that metric; otherwise the delta is None.
        """
        stmt = (
            select(GrowthMeasurement)
            .where(
                GrowthMeasurement.baby_id == baby_id,
                GrowthMeasurement.deleted_at.is_(None),
            )
            .order_by(
                GrowthMeasurement.measured_at.desc(),
                GrowthMeasurement.id.desc(),
            )
            .limit(2)
        )
        rows = list((await self._db.execute(stmt)).scalars().all())
        if not rows:
            return GrowthSummary()
        latest = rows[0]
        previous = rows[1] if len(rows) > 1 else None

        def _delta(attr: str) -> float | None:
            if previous is None:
                return None
            cur = getattr(latest, attr)
            prev = getattr(previous, attr)
            if cur is None or prev is None:
                return None
            return round(cur - prev, 4)

        return GrowthSummary(
            last_measured_at=latest.measured_at,
            weight_kg_delta=_delta("weight_kg"),
            height_cm_delta=_delta("height_cm"),
        )

    async def soft_delete(self, baby: Baby, *, owner: User) -> None:
        """Soft-delete `baby`. If it was the active baby, atomically reassign
        the owner's `active_baby_id` to their most-recently-added remaining
        baby (created_at DESC), or `NULL` if no others remain.

        Reassignment is part of the same flush as the soft-delete so the
        invariant "active_baby_id is either NULL or points at a live owned
        baby" never breaks mid-transaction. See FR-017 / data-model §
        "Atomic active-baby fallback".
        """
        now = _utcnow_iso()
        baby.deleted_at = now
        baby.updated_at = now
        if owner.active_baby_id == baby.id:
            stmt = (
                select(Baby)
                .where(
                    Baby.owner_user_id == owner.id,
                    Baby.deleted_at.is_(None),
                    Baby.id != baby.id,
                )
                .order_by(Baby.created_at.desc(), Baby.id.desc())
                .limit(1)
            )
            fallback = (await self._db.execute(stmt)).scalar_one_or_none()
            owner.active_baby_id = fallback.id if fallback is not None else None
            owner.updated_at = now
        await self._db.flush()

    async def set_active(self, owner: User, baby: Baby) -> None:
        if owner.active_baby_id == baby.id:
            return
        owner.active_baby_id = baby.id
        owner.updated_at = _utcnow_iso()
        await self._db.flush()
