"""add company priority

Revision ID: 20260711_0006
Revises: 20260710_0005
Create Date: 2026-07-11 00:06:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260711_0006"
down_revision: Union[str, None] = "20260710_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("priority", sa.String(length=20), server_default="medium", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("companies", "priority")
