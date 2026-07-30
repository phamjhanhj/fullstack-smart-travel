"""P1 notifications, journal and collections.

Revision ID: 0010_p1_experience
Revises: 0009_activity_lock
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_p1_experience"
down_revision = "0009_activity_lock"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("user_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False), sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False), sa.Column("action_url", sa.Text()),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("dedupe_key", sa.String(200), nullable=False), sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "dedupe_key", name="uq_user_notifications_dedupe"))
    op.create_index("ix_user_notifications_user_id", "user_notifications", ["user_id"])
    op.create_index("ix_user_notifications_created_at", "user_notifications", ["created_at"])
    op.create_table("trip_journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("activities.id", ondelete="SET NULL")),
        sa.Column("entry_date", sa.Date(), nullable=False), sa.Column("note", sa.Text()),
        sa.Column("photo_urls", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("actual_cost", sa.Integer()), sa.Column("rating", sa.Integer()),
        sa.Column("is_check_in", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True)))
    op.create_index("ix_trip_journal_entries_trip_id", "trip_journal_entries", ["trip_id"])
    op.create_table("saved_trip_collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False), sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_saved_collections_user_name"))
    op.create_table("saved_trip_collection_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saved_trip_collections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("publication_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("public_trip_publications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("collection_id", "publication_id", name="uq_collection_publication"))


def downgrade() -> None:
    op.drop_table("saved_trip_collection_items")
    op.drop_table("saved_trip_collections")
    op.drop_table("trip_journal_entries")
    op.drop_table("user_notifications")
