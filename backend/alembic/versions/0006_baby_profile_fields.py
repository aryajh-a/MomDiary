"""feature 010: baby profile detail fields.

Adds three nullable columns to the `babies` table so each baby can carry its
profile attributes: `gender`, `weight_kg`, `height_cm`. All are nullable with
no backfill — existing rows stay valid. (Blood type was dropped from scope for
HIPAA reasons.) Enum/range validation
lives in the Pydantic request schemas (schemas/babies.py), not as DB CHECK
constraints, so these are plain typed columns (no batch table-rebuild).

See specs/010-baby-profile/data-model.md.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("babies", sa.Column("gender", sa.String(), nullable=True))
    op.add_column("babies", sa.Column("weight_kg", sa.Float(), nullable=True))
    op.add_column("babies", sa.Column("height_cm", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("babies", "height_cm")
    op.drop_column("babies", "weight_kg")
    op.drop_column("babies", "gender")
