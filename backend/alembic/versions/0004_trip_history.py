from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_trip_history"
down_revision = "0003_trip_sharing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trip_history_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_trip_history_trip_created_at", "trip_history_events", ["trip_id", "created_at"])
    op.create_index("ix_trip_history_actor_user_id", "trip_history_events", ["actor_user_id"])
    op.create_index("ix_trip_history_entity", "trip_history_events", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_index("ix_trip_history_entity", table_name="trip_history_events")
    op.drop_index("ix_trip_history_actor_user_id", table_name="trip_history_events")
    op.drop_index("ix_trip_history_trip_created_at", table_name="trip_history_events")
    op.drop_table("trip_history_events")
