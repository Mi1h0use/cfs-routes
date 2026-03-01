"""Widen pdf_data from BLOB to MEDIUMBLOB

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "airac_cycle_pdfs",
        "pdf_data",
        existing_type=sa.LargeBinary(),
        type_=sa.LargeBinary(length=16_777_215),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "airac_cycle_pdfs",
        "pdf_data",
        existing_type=sa.LargeBinary(length=16_777_215),
        type_=sa.LargeBinary(),
        nullable=False,
    )
