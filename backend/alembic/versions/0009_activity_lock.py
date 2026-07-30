"""Persist user-controlled activity locks.

Revision ID: 0009_activity_lock
Revises: 0008_email_verification
"""
from alembic import op
import sqlalchemy as sa


revision = "0009_activity_lock"
down_revision = "0008_email_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("activities", "is_locked")
