"""Public user profiles.

Revision ID: 0012_public_profiles
Revises: 0011_p2_community
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_public_profiles"
down_revision = "0011_p2_community"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("users", sa.Column("is_public_profile", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("accepts_tour_bookings", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("public_bio", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("public_phone", sa.String(length=30), nullable=True))
    op.add_column("users", sa.Column("public_zalo_url", sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column("users", "public_zalo_url")
    op.drop_column("users", "public_phone")
    op.drop_column("users", "public_bio")
    op.drop_column("users", "accepts_tour_bookings")
    op.drop_column("users", "is_public_profile")