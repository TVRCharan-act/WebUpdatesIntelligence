"""add company watch type

Revision ID: 20260710_0006
Revises: 20260710_0005
Create Date: 2026-07-10 00:06:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260710_0006"
down_revision: Union[str, None] = "20260710_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("watch_type", sa.String(length=50), server_default="general", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("companies", "watch_type")
