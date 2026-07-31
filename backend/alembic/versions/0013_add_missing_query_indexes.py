"""Add non-destructive indexes used by P1/P2 query paths.

Revision ID: 0013_add_missing_query_indexes
Revises: 0012_public_profiles
"""
from alembic import op

revision = "0013_add_missing_query_indexes"
down_revision = "0012_public_profiles"
branch_labels = None
depends_on = None

INDEXES = [
    ("ix_user_notifications_type", "user_notifications", ["type"]),
    ("ix_trip_journal_entries_user_id", "trip_journal_entries", ["user_id"]),
    ("ix_trip_journal_entries_activity_id", "trip_journal_entries", ["activity_id"]),
    ("ix_trip_journal_entries_entry_date", "trip_journal_entries", ["entry_date"]),
    ("ix_saved_trip_collections_user_id", "saved_trip_collections", ["user_id"]),
    ("ix_saved_trip_collection_items_collection_id", "saved_trip_collection_items", ["collection_id"]),
    ("ix_saved_trip_collection_items_publication_id", "saved_trip_collection_items", ["publication_id"]),
    ("ix_public_trip_comments_publication_id", "public_trip_comments", ["publication_id"]),
    ("ix_public_trip_comments_user_id", "public_trip_comments", ["user_id"]),
    ("ix_public_trip_ratings_publication_id", "public_trip_ratings", ["publication_id"]),
    ("ix_public_trip_ratings_user_id", "public_trip_ratings", ["user_id"]),
    ("ix_author_follows_follower_user_id", "author_follows", ["follower_user_id"]),
    ("ix_author_follows_author_user_id", "author_follows", ["author_user_id"]),
    ("ix_hidden_recommendations_user_id", "hidden_recommendations", ["user_id"]),
    ("ix_hidden_recommendations_publication_id", "hidden_recommendations", ["publication_id"]),
]

def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns, unique=False)

def downgrade() -> None:
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)