"""P2 ratings, comments, follows and recommendations.

Revision ID: 0011_p2_community
Revises: 0010_p1_experience
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision="0011_p2_community"; down_revision="0010_p1_experience"; branch_labels=None; depends_on=None

def upgrade() -> None:
    op.create_table("public_trip_comments", sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True), sa.Column("publication_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("public_trip_publications.id",ondelete="CASCADE"),nullable=False), sa.Column("user_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False), sa.Column("content",sa.Text(),nullable=False), sa.Column("is_verified_trip",sa.Boolean(),nullable=False,server_default=sa.false()), sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_table("public_trip_ratings", sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True), sa.Column("publication_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("public_trip_publications.id",ondelete="CASCADE"),nullable=False), sa.Column("user_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False), sa.Column("rating",sa.Integer(),nullable=False), sa.Column("is_verified_trip",sa.Boolean(),nullable=False,server_default=sa.false()), sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()), sa.UniqueConstraint("publication_id","user_id",name="uq_public_rating_user"))
    op.create_table("author_follows", sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True), sa.Column("follower_user_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False), sa.Column("author_user_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False), sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()), sa.UniqueConstraint("follower_user_id","author_user_id",name="uq_author_follow"))
    op.create_table("hidden_recommendations", sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True), sa.Column("user_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False), sa.Column("publication_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("public_trip_publications.id",ondelete="CASCADE"),nullable=False), sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()), sa.UniqueConstraint("user_id","publication_id",name="uq_hidden_recommendation"))

def downgrade() -> None:
    op.drop_table("hidden_recommendations"); op.drop_table("author_follows"); op.drop_table("public_trip_ratings"); op.drop_table("public_trip_comments")
