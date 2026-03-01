"""Drop fir_sections table

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-28
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("fir_sections")


def downgrade() -> None:
    op.create_table(
        "fir_sections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=False),
        sa.Column("fir_code", sa.String(4), nullable=False),
        sa.Column("fir_name", sa.String(64), nullable=False),
        sa.Column("preamble_text", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["cycle_id"], ["airac_cycles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", "fir_code"),
    )
