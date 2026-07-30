from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_grounded_places"
down_revision = "0004_trip_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = [
        sa.Column("source_dataset_id", sa.String(), nullable=True),
        sa.Column("source_place_id", sa.String(), nullable=True),
        sa.Column("dataset_version", sa.String(), nullable=True),
        sa.Column("province_code", sa.String(), nullable=True),
        sa.Column("province_name", sa.String(), nullable=True),
        sa.Column("district", sa.String(), nullable=True),
        sa.Column("ward", sa.String(), nullable=True),
        sa.Column("subcategory", sa.String(), nullable=True),
        sa.Column("raw_category", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("suitable_for", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("typical_visit_minutes", sa.Integer(), nullable=True),
        sa.Column("opening_hours", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("price", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("contact", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("booking", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("constraints", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("verification", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("data_confidence", sa.String(), nullable=True),
        sa.Column("coordinate_status", sa.String(), nullable=True),
        sa.Column("coordinate_accuracy_meters", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]
    for column in columns:
        op.add_column("locations", column)

    op.create_unique_constraint(
        "uq_locations_source_dataset_place",
        "locations",
        ["source_dataset_id", "source_place_id"],
    )
    op.create_index(
        "ix_locations_province_category_status",
        "locations",
        ["province_code", "category", "status"],
    )
    op.create_index("ix_locations_province_name", "locations", ["province_name"])
    op.create_index("ix_locations_name", "locations", ["name"])


def downgrade() -> None:
    op.drop_index("ix_locations_name", table_name="locations")
    op.drop_index("ix_locations_province_name", table_name="locations")
    op.drop_index("ix_locations_province_category_status", table_name="locations")
    op.drop_constraint("uq_locations_source_dataset_place", "locations", type_="unique")
    for name in [
        "updated_at",
        "imported_at",
        "last_verified_at",
        "status",
        "coordinate_accuracy_meters",
        "coordinate_status",
        "data_confidence",
        "sources",
        "verification",
        "constraints",
        "booking",
        "contact",
        "price",
        "opening_hours",
        "typical_visit_minutes",
        "suitable_for",
        "tags",
        "description",
        "raw_category",
        "subcategory",
        "ward",
        "district",
        "province_name",
        "province_code",
        "dataset_version",
        "source_place_id",
        "source_dataset_id",
    ]:
        op.drop_column("locations", name)
