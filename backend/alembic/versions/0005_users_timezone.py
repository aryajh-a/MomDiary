"""feature 009: add users.timezone column.

Adds a nullable IANA-timezone column to the `users` table. The browser
captures it via `PATCH /v1/users/me` after Clerk sign-in (see Feature 009
plan). NULL means "fall back to the system default timezone" — no backfill
is required.

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("timezone", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "timezone")
