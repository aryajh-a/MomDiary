"""feature 009: Postgres baseline.

This revision is the single, idempotent schema-from-zero for the Postgres
runtime. It supersedes the SQLite history (0001..0003); those revisions are
retained on disk only as historical reference. Per the constitution
(`/speckit.plan` Decision: hard cutover, FR-013), there is no data carryover
from the SQLite era — production caregivers must re-sign-up through Clerk
and re-create their diary entries.

What this revision creates:

* Identity & profiles: `users`, `babies`
* Diary entries (all baby-scoped): `feeds`, `sleeps`, `poops`,
  `appointments`, `appointment_notes`
* Agent observability: `agent_interactions`
* Per-process singleton: `settings`
* Feature 009 new table: `chat_sessions` (JSONB turns, restart-survivable)

Revision ID: 0004
Revises:
Create Date: 2026-06-02
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
# Baseline: this revision intentionally has no parent. Existing Postgres
# databases that were stood up via 0001..0003 (SQLite-only) are not
# upgrade-compatible; fresh databases start here.
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("clerk_user_id", sa.String, nullable=False),
        sa.Column("email", sa.String, nullable=False),
        sa.Column("display_name", sa.String, nullable=False),
        sa.Column("email_verified_at", sa.Text, nullable=True),
        # active_baby_id FK is added after `babies` exists (forward ref).
        sa.Column("active_baby_id", sa.Integer, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.Column("deleted_at", sa.Text, nullable=True),
        sa.CheckConstraint(
            "length(display_name) >= 1 AND length(display_name) <= 80",
            name="ck_users_display_name_len",
        ),
    )
    op.create_index(
        "uq_users_clerk_user_id", "users", ["clerk_user_id"], unique=True
    )
    op.create_index("ix_users_deleted", "users", ["deleted_at"])

    # ------------------------------------------------------------------
    # babies
    # ------------------------------------------------------------------
    op.create_table(
        "babies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "owner_user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String, nullable=False),
        sa.Column("date_of_birth", sa.Text, nullable=False),
        sa.Column("color_tag", sa.String, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.Column("deleted_at", sa.Text, nullable=True),
        sa.CheckConstraint(
            "length(display_name) >= 1 AND length(display_name) <= 80",
            name="ck_babies_display_name_len",
        ),
        sa.CheckConstraint(
            "color_tag IS NULL OR length(color_tag) <= 16",
            name="ck_babies_color_tag_len",
        ),
    )
    op.create_index(
        "ix_babies_owner_deleted", "babies", ["owner_user_id", "deleted_at"]
    )

    # Now that `babies` exists, wire up the deferred users.active_baby_id FK.
    op.create_foreign_key(
        "fk_users_active_baby_id",
        source_table="users",
        referent_table="babies",
        local_cols=["active_baby_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )

    # ------------------------------------------------------------------
    # feeds
    # ------------------------------------------------------------------
    op.create_table(
        "feeds",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "baby_id",
            sa.Integer,
            sa.ForeignKey("babies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
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
    op.create_index(
        "ix_feeds_baby_occurred",
        "feeds",
        ["baby_id", "occurred_at", "deleted_at"],
    )

    # ------------------------------------------------------------------
    # sleeps
    # ------------------------------------------------------------------
    op.create_table(
        "sleeps",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "baby_id",
            sa.Integer,
            sa.ForeignKey("babies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("caregiver_id", sa.String, nullable=True),
        sa.Column("start_at", sa.Text, nullable=False),
        sa.Column("end_at", sa.Text, nullable=False),
        sa.Column("deleted_at", sa.Text, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.CheckConstraint(
            "end_at <> start_at", name="ck_sleeps_distinct_endpoints"
        ),
    )
    op.create_index(
        "ix_sleeps_deleted_start", "sleeps", ["deleted_at", "start_at"]
    )
    op.create_index(
        "ix_sleeps_baby_start", "sleeps", ["baby_id", "start_at", "deleted_at"]
    )

    # ------------------------------------------------------------------
    # poops
    # ------------------------------------------------------------------
    op.create_table(
        "poops",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "baby_id",
            sa.Integer,
            sa.ForeignKey("babies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
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
    op.create_index(
        "ix_poops_deleted_occurred", "poops", ["deleted_at", "occurred_at"]
    )
    op.create_index(
        "ix_poops_baby_occurred",
        "poops",
        ["baby_id", "occurred_at", "deleted_at"],
    )

    # ------------------------------------------------------------------
    # appointments + appointment_notes
    # ------------------------------------------------------------------
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "baby_id",
            sa.Integer,
            sa.ForeignKey("babies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
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
    op.create_index(
        "ix_appointments_baby_scheduled",
        "appointments",
        ["baby_id", "scheduled_at", "deleted_at"],
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

    # ------------------------------------------------------------------
    # agent_interactions
    # ------------------------------------------------------------------
    op.create_table(
        "agent_interactions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "baby_id",
            sa.Integer,
            sa.ForeignKey("babies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
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
    op.create_index(
        "ix_agent_int_created", "agent_interactions", ["created_at"]
    )
    op.create_index(
        "ix_agent_int_baby_created",
        "agent_interactions",
        ["baby_id", "created_at"],
    )

    # ------------------------------------------------------------------
    # settings (singleton)
    # ------------------------------------------------------------------
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
        ).bindparams(
            tz=default_tz,
            now=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
    )

    # ------------------------------------------------------------------
    # chat_sessions (feature 009 — restart-survivable SessionStore)
    # ------------------------------------------------------------------
    # `session_id` is the opaque UUID4 minted by InMemorySessionStore /
    # PgSessionStore. `user_id` mirrors the existing in-memory partition key
    # (integer, app-internal users.id) so cross-caregiver leakage is
    # impossible (FR-009 + 006-FR-017). `turns` is the entire bounded deque
    # serialised as JSONB on every write — this matches the existing
    # whole-session contract (deque length is bounded by max_turns * 2).
    op.create_table(
        "chat_sessions",
        sa.Column("session_id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("baby_id", sa.Integer, nullable=False),
        sa.Column(
            "turns",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    # Lookup by (caregiver, baby) for the dispatcher's partition check;
    # ordered DESC by recency to back the LRU eviction view (FR-011).
    op.create_index(
        "ix_chat_sessions_partition_recent",
        "chat_sessions",
        ["user_id", "baby_id", sa.text("updated_at DESC")],
    )
    # Plain index on updated_at for the TTL sweeper's range scan (FR-010).
    op.create_index(
        "ix_chat_sessions_updated_at", "chat_sessions", ["updated_at"]
    )


def downgrade() -> None:
    # Drop in reverse FK order. `chat_sessions` is independent.
    op.drop_index(
        "ix_chat_sessions_updated_at", table_name="chat_sessions"
    )
    op.drop_index(
        "ix_chat_sessions_partition_recent", table_name="chat_sessions"
    )
    op.drop_table("chat_sessions")

    op.drop_table("settings")

    op.drop_index("ix_agent_int_baby_created", table_name="agent_interactions")
    op.drop_index("ix_agent_int_created", table_name="agent_interactions")
    op.drop_index("ix_agent_int_correlation", table_name="agent_interactions")
    op.drop_table("agent_interactions")

    op.drop_index("ix_appt_notes_appt_added", table_name="appointment_notes")
    op.drop_table("appointment_notes")

    op.drop_index(
        "ix_appointments_baby_scheduled", table_name="appointments"
    )
    op.drop_index(
        "ix_appointments_deleted_scheduled", table_name="appointments"
    )
    op.drop_table("appointments")

    op.drop_index("ix_poops_baby_occurred", table_name="poops")
    op.drop_index("ix_poops_deleted_occurred", table_name="poops")
    op.drop_table("poops")

    op.drop_index("ix_sleeps_baby_start", table_name="sleeps")
    op.drop_index("ix_sleeps_deleted_start", table_name="sleeps")
    op.drop_table("sleeps")

    op.drop_index("ix_feeds_baby_occurred", table_name="feeds")
    op.drop_index("ix_feeds_deleted_occurred", table_name="feeds")
    op.drop_table("feeds")

    op.drop_constraint(
        "fk_users_active_baby_id", "users", type_="foreignkey"
    )
    op.drop_index("ix_babies_owner_deleted", table_name="babies")
    op.drop_table("babies")

    op.drop_index("ix_users_deleted", table_name="users")
    op.drop_index("uq_users_clerk_user_id", table_name="users")
    op.drop_table("users")
