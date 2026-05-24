"""Baby CRUD service — feature 006.

All queries are scoped to `owner_user_id`. Soft-delete sets `deleted_at` and
clears the owner's `active_baby_id` if it pointed at the deleted baby.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.models.orm import Baby, User
from momdiary.schemas.babies import BabyCreate, BabyUpdate


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
        if changed:
            baby.updated_at = _utcnow_iso()
            await self._db.flush()
        return baby

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
