"""ORM models for trip sharing and invitations."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class TripParticipant(Base):
    __tablename__ = "trip_participants"
    __table_args__ = (UniqueConstraint("trip_id", "user_id", name="uq_trip_participants_trip_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("trips.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)  # viewer | editor
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    trip: Mapped["Trip"] = relationship(back_populates="participants")
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    invited_by: Mapped["User"] = relationship(foreign_keys=[invited_by_user_id])


class TripShareInvite(Base):
    __tablename__ = "trip_share_invites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("trips.id"), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)  # viewer | editor
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")  # pending | accepted | revoked
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    accepted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    trip: Mapped["Trip"] = relationship(back_populates="share_invites")
    invited_by: Mapped["User"] = relationship(foreign_keys=[invited_by_user_id])
    accepted_by: Mapped["User"] = relationship(foreign_keys=[accepted_by_user_id])


from app.models.trip import Trip  # noqa: E402
from app.models.user import User  # noqa: E402
