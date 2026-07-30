"""Use a unique username as the authentication identifier."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_username_auth"
down_revision = "0006_public_trip_publications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=39), nullable=True))
    op.execute(
        """
        WITH candidates AS (
            SELECT id, LEFT(COALESCE(NULLIF(TRIM(BOTH '-' FROM REGEXP_REPLACE(
                LOWER(SPLIT_PART(email, '@', 1)), '[^a-z0-9-]+', '-', 'g'
            )), ''), 'user'), 30) AS base
            FROM users
        ), ranked AS (
            SELECT id, base, COUNT(*) OVER (PARTITION BY base) AS duplicate_count
            FROM candidates
        )
        UPDATE users AS u
        SET username = CASE
            WHEN ranked.duplicate_count = 1 THEN ranked.base
            ELSE ranked.base || '-' || LEFT(REPLACE(u.id::text, '-', ''), 8)
        END
        FROM ranked
        WHERE ranked.id = u.id
        """
    )
    op.alter_column("users", "username", nullable=False)
    op.alter_column("users", "email", existing_type=sa.String(), nullable=True)
    op.create_index("ix_users_username", "users", [sa.text("lower(username)")], unique=True)


def downgrade() -> None:
    op.execute("UPDATE users SET email = username || '@username.local' WHERE email IS NULL")
    op.drop_index("ix_users_username", table_name="users")
    op.alter_column("users", "email", existing_type=sa.String(), nullable=False)
    op.drop_column("users", "username")
