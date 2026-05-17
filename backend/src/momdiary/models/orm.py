"""SQLAlchemy ORM models — see specs/001-baby-tracker-backend/data-model.md."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
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


class Feed(Base):
    __tablename__ = "feeds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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
    )


class Sleep(Base):
    __tablename__ = "sleeps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    caregiver_id: Mapped[str | None] = mapped_column(String, nullable=True)
    start_at: Mapped[str] = mapped_column(Text, nullable=False)
    end_at: Mapped[str] = mapped_column(Text, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=_utcnow_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=_utcnow_iso)

    __table_args__ = (
        CheckConstraint("end_at <> start_at", name="ck_sleeps_distinct_endpoints"),
        Index("ix_sleeps_deleted_start", "deleted_at", "start_at"),
    )


class Poop(Base):
    __tablename__ = "poops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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
    )


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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
    )


class SettingsRow(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    default_timezone: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=_utcnow_iso)

    __table_args__ = (CheckConstraint("id = 1", name="ck_settings_singleton"),)
