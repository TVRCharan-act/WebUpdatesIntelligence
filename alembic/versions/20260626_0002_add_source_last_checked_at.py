"""add source last checked timestamp

Revision ID: 20260626_0002
Revises: 20260626_0001
Create Date: 2026-06-26 00:01:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260626_0002"
down_revision: Union[str, None] = "20260626_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sources", "last_checked_at")
