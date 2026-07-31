"""Add paid_by and participants columns to budget_items table.

Revision ID: 0017_budget_item_splits
Revises: 0016_community_safety
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0017_budget_item_splits"
down_revision = "0016_community_safety"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("budget_items", sa.Column("paid_by", sa.String(), nullable=True))
    op.add_column("budget_items", sa.Column("participants", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("budget_items", "participants")
    op.drop_column("budget_items", "paid_by")
