from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_trip_sharing"
down_revision = "0002_refresh_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trip_participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trips.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("invited_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("trip_id", "user_id", name="uq_trip_participants_trip_user"),
    )
    op.create_index("ix_trip_participants_trip_id", "trip_participants", ["trip_id"])
    op.create_index("ix_trip_participants_user_id", "trip_participants", ["user_id"])

    op.create_table(
        "trip_share_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trips.id"), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("invited_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("accepted_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_trip_share_invites_trip_id", "trip_share_invites", ["trip_id"])
    op.create_index("ix_trip_share_invites_email", "trip_share_invites", ["email"])
    op.create_index("ix_trip_share_invites_token_hash", "trip_share_invites", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_trip_share_invites_token_hash", table_name="trip_share_invites")
    op.drop_index("ix_trip_share_invites_email", table_name="trip_share_invites")
    op.drop_index("ix_trip_share_invites_trip_id", table_name="trip_share_invites")
    op.drop_table("trip_share_invites")
    op.drop_index("ix_trip_participants_user_id", table_name="trip_participants")
    op.drop_index("ix_trip_participants_trip_id", table_name="trip_participants")
    op.drop_table("trip_participants")
