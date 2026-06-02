"""feature 007: add users.timezone column.

Adds a nullable IANA-timezone column to the `users` table. The browser
populates it via the register/login payloads (see Feature 007 plan §"API
changes"). No backfill — pre-feature accounts were deleted from the dev
DB before this migration was created, so this revision starts against
zero user rows in dev.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("timezone", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "timezone")
