"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-01-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "airac_cycles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cycle_ident", sa.String(4), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("pdf_url", sa.String(512), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.Column("parsed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "fetched", "parsed", "failed", name="cyclestatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_ident"),
    )

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

    op.create_table(
        "mandatory_routes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=False),
        sa.Column("fir_code", sa.String(4), nullable=False),
        sa.Column("airport", sa.String(4), nullable=False),
        sa.Column("altitude", sa.String(8), nullable=False),
        sa.Column("direction_type", sa.String(4), nullable=False),
        sa.Column("direction", sa.String(4), nullable=False, server_default=""),
        sa.Column("destination", sa.String(4), nullable=True),
        sa.Column("limitations", sa.Text(), nullable=True),
        sa.Column("procedure", sa.String(16), nullable=True),
        sa.Column("route", sa.Text(), nullable=False),
        sa.Column("raw_line", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["cycle_id"], ["airac_cycles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mr_cycle_airport", "mandatory_routes", ["cycle_id", "airport"])
    op.create_index(
        "ix_mr_cycle_airport_dir",
        "mandatory_routes",
        ["cycle_id", "airport", "direction_type"],
    )
    op.create_index("ix_mr_cycle_dest", "mandatory_routes", ["cycle_id", "destination"])


def downgrade() -> None:
    op.drop_table("mandatory_routes")
    op.drop_table("fir_sections")
    op.drop_table("airac_cycles")
