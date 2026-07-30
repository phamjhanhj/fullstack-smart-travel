from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_public_trip_publications"
down_revision = "0005_grounded_places"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_trip_publications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_trip_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trips.id", ondelete="SET NULL"), nullable=True),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(240), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("destination", sa.String(200), nullable=False),
        sa.Column("province_name", sa.String(120), nullable=True),
        sa.Column("cover_image_url", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(20), nullable=False, server_default="public"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("moderation_status", sa.String(20), nullable=False, server_default="approved"),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("travel_month", sa.Integer(), nullable=True),
        sa.Column("travel_year", sa.Integer(), nullable=True),
        sa.Column("traveler_type", sa.String(40), nullable=True),
        sa.Column("pace", sa.String(30), nullable=True),
        sa.Column("budget_style", sa.String(30), nullable=True),
        sa.Column("actual_total_cost", sa.BigInteger(), nullable=True),
        sa.Column("actual_cost_per_person", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False, server_default="VND"),
        sa.Column("cost_is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("itinerary_rating", sa.Integer(), nullable=True),
        sa.Column("cost_rating", sa.Integer(), nullable=True),
        sa.Column("place_rating", sa.Integer(), nullable=True),
        sa.Column("overall_rating", sa.Numeric(2, 1), nullable=True),
        sa.Column("snapshot_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("snapshot_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("privacy_options", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("allow_clone", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_partial_import", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_comments", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("save_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("clone_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("comment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("author_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_public_trip_publications_slug", "public_trip_publications", ["slug"], unique=True)
    op.create_index("ix_public_trip_publications_source_trip_id", "public_trip_publications", ["source_trip_id"])
    op.create_index("ix_public_trip_publications_author_user_id", "public_trip_publications", ["author_user_id"])
    op.create_index("ix_public_trip_publications_destination", "public_trip_publications", ["destination"])
    op.create_index("ix_public_trip_publications_province_name", "public_trip_publications", ["province_name"])
    op.create_index("ix_public_trip_publications_status", "public_trip_publications", ["status"])
    op.create_index(
        "uq_public_trip_active_source",
        "public_trip_publications",
        ["source_trip_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('draft', 'published') AND source_trip_id IS NOT NULL"),
    )

    op.create_table(
        "public_trip_saves",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("publication_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("public_trip_publications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("publication_id", "user_id", name="uq_public_trip_saves_publication_user"),
    )
    op.create_index("ix_public_trip_saves_publication_id", "public_trip_saves", ["publication_id"])
    op.create_index("ix_public_trip_saves_user_id", "public_trip_saves", ["user_id"])

    op.create_table(
        "public_trip_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("publication_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("public_trip_publications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_trip_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("import_mode", sa.String(20), nullable=False),
        sa.Column("source_day_number", sa.Integer(), nullable=True),
        sa.Column("source_activity_key", sa.String(80), nullable=True),
        sa.Column("target_day_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("day_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_public_trip_imports_publication_id", "public_trip_imports", ["publication_id"])
    op.create_index("ix_public_trip_imports_target_trip_id", "public_trip_imports", ["target_trip_id"])
    op.create_index("ix_public_trip_imports_user_id", "public_trip_imports", ["user_id"])

    op.create_table(
        "activity_publication_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("publication_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("public_trip_publications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snapshot_version", sa.Integer(), nullable=False),
        sa.Column("source_day_number", sa.Integer(), nullable=False),
        sa.Column("source_activity_key", sa.String(80), nullable=False),
        sa.Column("imported_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("author_verdict", sa.String(30), nullable=True),
        sa.Column("author_note_snapshot", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_activity_publication_sources_publication_id", "activity_publication_sources", ["publication_id"])


def downgrade() -> None:
    op.drop_table("activity_publication_sources")
    op.drop_table("public_trip_imports")
    op.drop_table("public_trip_saves")
    op.drop_index("uq_public_trip_active_source", table_name="public_trip_publications")
    op.drop_table("public_trip_publications")
