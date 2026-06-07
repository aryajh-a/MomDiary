"""SQLAlchemy ORM models — see specs/001-baby-tracker-backend/data-model.md
and specs/006-user-and-baby-profiles/data-model.md."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Feature 006 — Caregiver accounts & baby profiles
# ---------------------------------------------------------------------------


class User(Base):
    """A caregiver account.

    Feature 008 rewrite: identity is now anchored to a Clerk user
    (`clerk_user_id`, unique, not-null). The `password_hash` and
    `password_updated_at` columns from feature 006 are removed; email +
    email-verification state are mirrored from the Clerk JWT on every
    sign-in (lazy provisioning lives in `auth.dependencies`).
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Clerk user id (`user_2abc...`), source of truth for identity.
    clerk_user_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    # NULL when Clerk reports the primary email is not yet verified.
    # Server-side write gate (require_verified_email) keys off this column.
    email_verified_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    active_baby_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("babies.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    # IANA zone name (e.g. "Asia/Kolkata"). Feature 009 — captured from the
    # browser via PATCH /v1/users/me. NULL means "fall back to the system
    # default timezone" (services.time_service.get_request_timezone).
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=_utcnow_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=_utcnow_iso)
    deleted_at: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "length(display_name) >= 1 AND length(display_name) <= 80",
            name="ck_users_display_name_len",
        ),
        # Unique case-insensitive index on email is created in the Alembic
        # revision (SQLite-specific COLLATE NOCASE).
        Index("ix_users_deleted", "deleted_at"),
    )


class Baby(Base):
    """A baby profile owned by exactly one user in v1 (FR-019)."""

    __tablename__ = "babies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    date_of_birth: Mapped[str] = mapped_column(Text, nullable=False)  # ISO date
    color_tag: Mapped[str | None] = mapped_column(String, nullable=True)
    # Feature 010 — baby profile detail. All nullable; existing rows stay
    # valid without backfill. Enum/range rules are enforced in the Pydantic
    # request schemas (schemas/babies.py), not as DB CHECK constraints
    # (see specs/010-baby-profile/data-model.md).
    gender: Mapped[str | None] = mapped_column(String, nullable=True)
    # Current snapshot (kg / cm), stored in display units — no conversion.
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=_utcnow_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=_utcnow_iso)
    deleted_at: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "length(display_name) >= 1 AND length(display_name) <= 80",
            name="ck_babies_display_name_len",
        ),
        CheckConstraint(
            "color_tag IS NULL OR length(color_tag) <= 16",
            name="ck_babies_color_tag_len",
        ),
        Index("ix_babies_owner_deleted", "owner_user_id", "deleted_at"),
    )


# ---------------------------------------------------------------------------
# Diary entries — every row scoped to a baby (FR-014 / FR-018)
# ---------------------------------------------------------------------------


class Feed(Base):
    __tablename__ = "feeds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    baby_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("babies.id", ondelete="RESTRICT"), nullable=False
    )
    caregiver_id: Mapped[str | None] = mapped_column(String, nullable=True)
    feed_type: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[float] = mapped_column(nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    occurred_at: Mapped[str] = mapped_column(Text, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=_utcnow_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=_utcnow_iso)

    __table_args__ = (
        CheckConstraint(
            "feed_type IN ('breast_milk', 'formula', 'solids', 'water')",
            name="ck_feeds_feed_type",
        ),
        CheckConstraint("quantity > 0", name="ck_feeds_quantity_positive"),
        CheckConstraint("unit IN ('ml', 'g')", name="ck_feeds_unit"),
        Index("ix_feeds_deleted_occurred", "deleted_at", "occurred_at"),
        Index("ix_feeds_baby_occurred", "baby_id", "occurred_at", "deleted_at"),
    )


class Sleep(Base):
    __tablename__ = "sleeps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    baby_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("babies.id", ondelete="RESTRICT"), nullable=False
    )
    caregiver_id: Mapped[str | None] = mapped_column(String, nullable=True)
    start_at: Mapped[str] = mapped_column(Text, nullable=False)
    end_at: Mapped[str] = mapped_column(Text, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=_utcnow_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=_utcnow_iso)

    __table_args__ = (
        CheckConstraint("end_at <> start_at", name="ck_sleeps_distinct_endpoints"),
        Index("ix_sleeps_deleted_start", "deleted_at", "start_at"),
        Index("ix_sleeps_baby_start", "baby_id", "start_at", "deleted_at"),
    )


class Poop(Base):
    __tablename__ = "poops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    baby_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("babies.id", ondelete="RESTRICT"), nullable=False
    )
    caregiver_id: Mapped[str | None] = mapped_column(String, nullable=True)
    occurred_at: Mapped[str] = mapped_column(Text, nullable=False)
    consistency: Mapped[str] = mapped_column(String, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=_utcnow_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=_utcnow_iso)

    __table_args__ = (
        CheckConstraint(
            "consistency IN ('watery', 'soft', 'formed', 'hard')",
            name="ck_poops_consistency",
        ),
        Index("ix_poops_deleted_occurred", "deleted_at", "occurred_at"),
        Index("ix_poops_baby_occurred", "baby_id", "occurred_at", "deleted_at"),
    )


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    baby_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("babies.id", ondelete="RESTRICT"), nullable=False
    )
    caregiver_id: Mapped[str | None] = mapped_column(String, nullable=True)
    scheduled_at: Mapped[str] = mapped_column(Text, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=_utcnow_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=_utcnow_iso)

    notes: Mapped[list[AppointmentNote]] = relationship(
        "AppointmentNote",
        back_populates="appointment",
        cascade="all, delete-orphan",
        order_by="AppointmentNote.added_at",
    )

    __table_args__ = (
        Index("ix_appointments_deleted_scheduled", "deleted_at", "scheduled_at"),
        Index(
            "ix_appointments_baby_scheduled",
            "baby_id",
            "scheduled_at",
            "deleted_at",
        ),
    )


class AppointmentNote(Base):
    __tablename__ = "appointment_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    added_at: Mapped[str] = mapped_column(Text, nullable=False, default=_utcnow_iso)

    appointment: Mapped[Appointment] = relationship(
        "Appointment", back_populates="notes"
    )

    __table_args__ = (
        CheckConstraint(
            "length(body) >= 1 AND length(body) <= 2000",
            name="ck_appt_notes_body_len",
        ),
        Index("ix_appt_notes_appt_added", "appointment_id", "added_at"),
    )


class AgentInteraction(Base):
    __tablename__ = "agent_interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    baby_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("babies.id", ondelete="RESTRICT"), nullable=False
    )
    correlation_id: Mapped[str] = mapped_column(String, nullable=False)
    inbound_message: Mapped[str] = mapped_column(Text, nullable=False)
    selected_tool: Mapped[str | None] = mapped_column(String, nullable=True)
    entry_type: Mapped[str | None] = mapped_column(String, nullable=True)
    entry_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    model_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=_utcnow_iso)

    __table_args__ = (
        CheckConstraint(
            "outcome IN ('created', 'updated', 'deleted', 'clarification_requested', 'rejected')",
            name="ck_agent_int_outcome",
        ),
        Index("ix_agent_int_correlation", "correlation_id"),
        Index("ix_agent_int_created", "created_at"),
        Index("ix_agent_int_baby_created", "baby_id", "created_at"),
    )


class GrowthMeasurement(Base):
    """A dated weight/height snapshot for a baby (feature 010 — growth history).

    One row per measurement event (date + weight + height together). The
    baby's `weight_kg` / `height_cm` columns cache the latest measurement for
    cheap list reads; this table is the history of record and backs the
    profile's delta ("↑0.3 kg" vs the previous measurement). Head circumference
    is intentionally not modelled.
    """

    __tablename__ = "growth_measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    baby_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("babies.id", ondelete="RESTRICT"), nullable=False
    )
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    measured_at: Mapped[str] = mapped_column(Text, nullable=False)  # ISO date
    deleted_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=_utcnow_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=_utcnow_iso)

    __table_args__ = (
        Index(
            "ix_growth_baby_measured",
            "baby_id",
            "measured_at",
            "deleted_at",
        ),
    )


class SettingsRow(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    default_timezone: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=_utcnow_iso)

    __table_args__ = (CheckConstraint("id = 1", name="ck_settings_singleton"),)
