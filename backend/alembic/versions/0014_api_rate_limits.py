"""Database-backed API rate-limit buckets.

Revision ID: 0014_api_rate_limits
Revises: 0013_add_missing_query_indexes
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_api_rate_limits"
down_revision = "0013_add_missing_query_indexes"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "api_rate_limit_buckets",
        sa.Column("scope", sa.String(80), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("window_start", sa.BigInteger(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("scope", "key_hash", "window_start", name="pk_api_rate_limit_buckets"),
    )
    op.create_index("ix_api_rate_limit_buckets_expires_at", "api_rate_limit_buckets", ["expires_at"])

def downgrade() -> None:
    op.drop_index("ix_api_rate_limit_buckets_expires_at", table_name="api_rate_limit_buckets")
    op.drop_table("api_rate_limit_buckets")