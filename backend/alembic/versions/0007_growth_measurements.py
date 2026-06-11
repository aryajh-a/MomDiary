"""feature 010: growth measurement history.

Adds the `growth_measurements` table — one dated weight/height snapshot per
measurement event. The baby's `weight_kg`/`height_cm` columns (added in 0006)
remain as the cached "current" value; this table is the history of record and
backs the profile's delta display. Head circumference is intentionally not
modelled.

See specs/010-baby-profile/data-model.md.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "growth_measurements",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "baby_id",
            sa.Integer,
            sa.ForeignKey("babies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("weight_kg", sa.Float, nullable=True),
        sa.Column("height_cm", sa.Float, nullable=True),
        sa.Column("measured_at", sa.Text, nullable=False),
        sa.Column("deleted_at", sa.Text, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
    )
    op.create_index(
        "ix_growth_baby_measured",
        "growth_measurements",
        ["baby_id", "measured_at", "deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_growth_baby_measured", table_name="growth_measurements")
    op.drop_table("growth_measurements")
