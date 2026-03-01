"""Add airac_cycle_pdfs table and make pdf_url nullable

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "airac_cycle_pdfs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "cycle_id",
            sa.Integer(),
            sa.ForeignKey("airac_cycles.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("pdf_data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.alter_column("airac_cycles", "pdf_url", existing_type=sa.String(512), nullable=True)


def downgrade() -> None:
    op.alter_column("airac_cycles", "pdf_url", existing_type=sa.String(512), nullable=False)
    op.drop_table("airac_cycle_pdfs")
