"""add summary confidence

Revision ID: 20260710_0005
Revises: 20260709_0004
Create Date: 2026-07-10 00:05:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260710_0005"
down_revision: Union[str, None] = "20260709_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "summaries",
        sa.Column("confidence", sa.String(length=50), server_default="medium", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("summaries", "confidence")
