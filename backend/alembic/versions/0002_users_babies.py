"""feature 006: caregiver accounts, baby profiles, baby-scoped diary tables.

DESTRUCTIVE MIGRATION: per FR-018, all pre-existing rows in `feeds`, `sleeps`,
`poops`, `appointments`, `appointment_notes`, and `agent_interactions` are
hard-deleted before adding the `baby_id NOT NULL` FK column.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. New tables: users, babies, user_sessions
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("display_name", sa.String, nullable=False),
        sa.Column("active_baby_id", sa.Integer, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.Column("deleted_at", sa.Text, nullable=True),
        sa.CheckConstraint(
            "length(display_name) >= 1 AND length(display_name) <= 80",
            name="ck_users_display_name_len",
        ),
    )
    # Case-insensitive UNIQUE on email (SQLite-specific COLLATE NOCASE).
    op.execute(
        "CREATE UNIQUE INDEX ux_users_email_nocase "
        "ON users (email COLLATE NOCASE)"
    )
    op.create_index("ix_users_deleted", "users", ["deleted_at"])

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

    # users.active_baby_id is a forward-reference (defined after babies).
    # SQLite can't ALTER ADD FK; we rely on render_as_batch handling, but
    # ORM-side `use_alter=True` means we leave the constraint enforced only at
    # the application layer for SQLite. (Acceptable per spec — single-process
    # SQLite, FK pragma is on at engine level.)

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("expires_at", sa.Text, nullable=False),
        sa.Column("last_seen_at", sa.Text, nullable=False),
        sa.Column("revoked_at", sa.Text, nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index(
        "ix_user_sessions_expires_at", "user_sessions", ["expires_at"]
    )

    # ------------------------------------------------------------------
    # 2. FR-018: hard-delete all pre-existing diary rows.
    # ------------------------------------------------------------------
    for table in (
        "agent_interactions",
        "appointment_notes",
        "appointments",
        "poops",
        "sleeps",
        "feeds",
    ):
        op.execute(f"DELETE FROM {table}")

    # ------------------------------------------------------------------
    # 3. Add baby_id NOT NULL FK to each diary table (SQLite => batch ALTER).
    #    Tables are empty (step 2), so the NOT NULL add is safe.
    #    Note: batch_alter_table in SQLite recreates the table; every
    #    constraint added inside the batch must carry an explicit name.
    # ------------------------------------------------------------------
    for table, time_col in (
        ("feeds", "occurred_at"),
        ("sleeps", "start_at"),
        ("poops", "occurred_at"),
        ("appointments", "scheduled_at"),
    ):
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.add_column(
                sa.Column(
                    "baby_id",
                    sa.Integer,
                    sa.ForeignKey(
                        "babies.id",
                        ondelete="RESTRICT",
                        name=f"fk_{table}_baby_id",
                    ),
                    nullable=False,
                )
            )
        op.create_index(
            f"ix_{table}_baby_{time_col.split('_')[0]}",
            table,
            ["baby_id", time_col, "deleted_at"],
        )

    with op.batch_alter_table("agent_interactions", recreate="always") as batch:
        batch.add_column(
            sa.Column(
                "baby_id",
                sa.Integer,
                sa.ForeignKey(
                    "babies.id",
                    ondelete="RESTRICT",
                    name="fk_agent_interactions_baby_id",
                ),
                nullable=False,
            )
        )
    op.create_index(
        "ix_agent_int_baby_created", "agent_interactions", ["baby_id", "created_at"]
    )


def downgrade() -> None:
    # Drop baby_id columns + new indexes from diary tables.
    for table in ("feeds", "sleeps", "poops", "appointments", "agent_interactions"):
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.drop_column("baby_id")

    op.drop_index("ix_user_sessions_expires_at", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")

    op.drop_index("ix_babies_owner_deleted", table_name="babies")
    op.drop_table("babies")

    op.drop_index("ix_users_deleted", table_name="users")
    op.execute("DROP INDEX IF EXISTS ux_users_email_nocase")
    op.drop_table("users")
