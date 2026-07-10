"""add account scoping and insight review

Revision ID: 20260709_0004
Revises: 20260629_0003
Create Date: 2026-07-09 00:04:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260709_0004"
down_revision: Union[str, None] = "20260629_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("owner_name", sa.String(length=255), nullable=True))
    op.create_index("ix_companies_owner_name", "companies", ["owner_name"])
    op.add_column(
        "summaries",
        sa.Column("severity", sa.String(length=50), server_default="medium", nullable=False),
    )
    op.add_column("summaries", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("summaries", "reviewed_at")
    op.drop_column("summaries", "severity")
    op.drop_index("ix_companies_owner_name", table_name="companies")
    op.drop_column("companies", "owner_name")
