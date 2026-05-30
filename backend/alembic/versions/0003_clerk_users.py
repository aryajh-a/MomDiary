"""feature 008: replace local password auth with Clerk-issued JWT identity.

HARD CUTOVER (FR-012, SC-004):
  * Every pre-existing diary row is deleted (caregivers must re-create
    their data after re-signing-up through Clerk).
  * The `user_sessions` table from feature 006 is dropped wholesale.
  * The `password_hash` column on `users` is dropped.
  * New columns on `users`:
      - `clerk_user_id`  TEXT NOT NULL UNIQUE  (Clerk `sub` claim)
      - `email_verified_at` TEXT NULL (server-side write gate keys off this)

Downgrade raises NotImplementedError — there is no path back to local
password auth once Clerk is the source of truth.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Hard-delete all pre-existing rows in FK-safe order (FR-012).
    #    Diary tables first (children → parents), then babies, then users,
    #    then the user_sessions table that's about to be dropped.
    # ------------------------------------------------------------------
    for table in (
        "appointment_notes",
        "appointments",
        "poops",
        "sleeps",
        "feeds",
        "agent_interactions",
        "babies",
        "user_sessions",
        "users",
    ):
        op.execute(f"DELETE FROM {table}")

    # ------------------------------------------------------------------
    # 2. Drop the user_sessions table entirely (cookie auth retired).
    # ------------------------------------------------------------------
    op.drop_index("ix_user_sessions_expires_at", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")

    # ------------------------------------------------------------------
    # 3. Rewrite users: drop password_hash, add clerk_user_id +
    #    email_verified_at. SQLite => batch ALTER recreates the table.
    # ------------------------------------------------------------------
    with op.batch_alter_table("users", recreate="always") as batch:
        batch.drop_column("password_hash")
        batch.add_column(
            sa.Column("clerk_user_id", sa.String, nullable=False)
        )
        batch.add_column(
            sa.Column("email_verified_at", sa.Text, nullable=True)
        )

    op.create_index(
        "uq_users_clerk_user_id",
        "users",
        ["clerk_user_id"],
        unique=True,
    )


def downgrade() -> None:
    raise NotImplementedError(
        "Feature 008 is a one-way migration: there is no downgrade path from "
        "Clerk identity back to local password authentication."
    )
