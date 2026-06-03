"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-16
"""

from __future__ import annotations

from datetime import datetime, timezone
import os

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feeds",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("caregiver_id", sa.String, nullable=True),
        sa.Column("feed_type", sa.String, nullable=False),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("unit", sa.String, nullable=False),
        sa.Column("occurred_at", sa.Text, nullable=False),
        sa.Column("deleted_at", sa.Text, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.CheckConstraint(
            "feed_type IN ('breast_milk', 'formula', 'solids', 'water')",
            name="ck_feeds_feed_type",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_feeds_quantity_positive"),
        sa.CheckConstraint("unit IN ('ml', 'g')", name="ck_feeds_unit"),
    )
    op.create_index(
        "ix_feeds_deleted_occurred", "feeds", ["deleted_at", "occurred_at"]
    )

    op.create_table(
        "sleeps",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("caregiver_id", sa.String, nullable=True),
        sa.Column("start_at", sa.Text, nullable=False),
        sa.Column("end_at", sa.Text, nullable=False),
        sa.Column("deleted_at", sa.Text, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.CheckConstraint("end_at <> start_at", name="ck_sleeps_distinct_endpoints"),
    )
    op.create_index("ix_sleeps_deleted_start", "sleeps", ["deleted_at", "start_at"])

    op.create_table(
        "poops",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("caregiver_id", sa.String, nullable=True),
        sa.Column("occurred_at", sa.Text, nullable=False),
        sa.Column("consistency", sa.String, nullable=False),
        sa.Column("deleted_at", sa.Text, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.CheckConstraint(
            "consistency IN ('watery', 'soft', 'formed', 'hard')",
            name="ck_poops_consistency",
        ),
    )
    op.create_index("ix_poops_deleted_occurred", "poops", ["deleted_at", "occurred_at"])

    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("caregiver_id", sa.String, nullable=True),
        sa.Column("scheduled_at", sa.Text, nullable=False),
        sa.Column("deleted_at", sa.Text, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
    )
    op.create_index(
        "ix_appointments_deleted_scheduled",
        "appointments",
        ["deleted_at", "scheduled_at"],
    )

    op.create_table(
        "appointment_notes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "appointment_id",
            sa.Integer,
            sa.ForeignKey("appointments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("added_at", sa.Text, nullable=False),
        sa.CheckConstraint(
            "length(body) >= 1 AND length(body) <= 2000",
            name="ck_appt_notes_body_len",
        ),
    )
    op.create_index(
        "ix_appt_notes_appt_added",
        "appointment_notes",
        ["appointment_id", "added_at"],
    )

    op.create_table(
        "agent_interactions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("correlation_id", sa.String, nullable=False),
        sa.Column("inbound_message", sa.Text, nullable=False),
        sa.Column("selected_tool", sa.String, nullable=True),
        sa.Column("entry_type", sa.String, nullable=True),
        sa.Column("entry_id", sa.Integer, nullable=True),
        sa.Column("outcome", sa.String, nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column("model_latency_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.CheckConstraint(
            "outcome IN ('created', 'updated', 'deleted', "
            "'clarification_requested', 'rejected')",
            name="ck_agent_int_outcome",
        ),
    )
    op.create_index(
        "ix_agent_int_correlation", "agent_interactions", ["correlation_id"]
    )
    op.create_index("ix_agent_int_created", "agent_interactions", ["created_at"])

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("default_timezone", sa.String, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.CheckConstraint("id = 1", name="ck_settings_singleton"),
    )

    default_tz = os.environ.get("MOMDIARY_DEFAULT_TIMEZONE", "America/Los_Angeles")
    op.execute(
        sa.text(
            "INSERT INTO settings (id, default_timezone, updated_at) "
            "VALUES (1, :tz, :now)"
        ).bindparams(tz=default_tz, now=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    )


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_index("ix_agent_int_created", table_name="agent_interactions")
    op.drop_index("ix_agent_int_correlation", table_name="agent_interactions")
    op.drop_table("agent_interactions")
    op.drop_index("ix_appt_notes_appt_added", table_name="appointment_notes")
    op.drop_table("appointment_notes")
    op.drop_index("ix_appointments_deleted_scheduled", table_name="appointments")
    op.drop_table("appointments")
    op.drop_index("ix_poops_deleted_occurred", table_name="poops")
    op.drop_table("poops")
    op.drop_index("ix_sleeps_deleted_start", table_name="sleeps")
    op.drop_table("sleeps")
    op.drop_index("ix_feeds_deleted_occurred", table_name="feeds")
    op.drop_table("feeds")
