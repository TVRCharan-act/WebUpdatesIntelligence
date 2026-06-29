"""add email delivery settings

Revision ID: 20260629_0003
Revises: 20260626_0002
Create Date: 2026-06-29 00:03:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260629_0003"
down_revision: Union[str, None] = "20260626_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "summaries",
        sa.Column(
            "email_status",
            sa.String(length=50),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column(
        "summaries",
        sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "summaries",
        sa.Column("email_error", sa.Text(), nullable=True),
    )
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )
    op.execute(
        "INSERT INTO app_settings (key, value) "
        "VALUES ('email_notification_mode', 'manual')"
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_column("summaries", "email_error")
    op.drop_column("summaries", "email_sent_at")
    op.drop_column("summaries", "email_status")
