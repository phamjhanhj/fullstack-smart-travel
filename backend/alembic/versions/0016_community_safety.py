"""Community reports and private booking inquiries."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "0016_community_safety"
down_revision = "0015_journal_privacy"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("community_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("reporter_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("publication_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("public_trip_publications.id", ondelete="CASCADE")),
        sa.Column("reported_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("reason", sa.String(40), nullable=False), sa.Column("details", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("(publication_id IS NOT NULL) <> (reported_user_id IS NOT NULL)", name="ck_report_exactly_one_target"),
        sa.UniqueConstraint("reporter_user_id", "publication_id", name="uq_reporter_publication"),
        sa.UniqueConstraint("reporter_user_id", "reported_user_id", name="uq_reporter_profile"))
    op.create_index("ix_community_reports_publication_id", "community_reports", ["publication_id"])
    op.create_index("ix_community_reports_reported_user_id", "community_reports", ["reported_user_id"])
    op.create_index("ix_community_reports_status", "community_reports", ["status"])
    op.create_table("tour_booking_inquiries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("publication_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("public_trip_publications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requester_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_name", sa.String(100), nullable=False), sa.Column("contact_phone", sa.String(30), nullable=False),
        sa.Column("travelers", sa.Integer(), nullable=False, server_default="1"), sa.Column("message", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True)))
    op.create_index("ix_booking_inquiries_author_created", "tour_booking_inquiries", ["author_user_id", "created_at"])
    op.create_index("ix_booking_inquiries_requester_created", "tour_booking_inquiries", ["requester_user_id", "created_at"])

def downgrade() -> None:
    op.drop_index("ix_booking_inquiries_requester_created", table_name="tour_booking_inquiries")
    op.drop_index("ix_booking_inquiries_author_created", table_name="tour_booking_inquiries")
    op.drop_table("tour_booking_inquiries")
    op.drop_index("ix_community_reports_status", table_name="community_reports")
    op.drop_index("ix_community_reports_reported_user_id", table_name="community_reports")
    op.drop_index("ix_community_reports_publication_id", table_name="community_reports")
    op.drop_table("community_reports")