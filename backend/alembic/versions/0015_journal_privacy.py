"""Private-by-default trip journal entries.

Revision ID: 0015_journal_privacy
Revises: 0014_api_rate_limits
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_journal_privacy"
down_revision = "0014_api_rate_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trip_journal_entries",
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_trip_journal_entries_trip_shared",
        "trip_journal_entries",
        ["trip_id", "is_shared"],
    )


def downgrade() -> None:
    op.drop_index("ix_trip_journal_entries_trip_shared", table_name="trip_journal_entries")
    op.drop_column("trip_journal_entries", "is_shared")