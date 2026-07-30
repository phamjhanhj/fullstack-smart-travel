"""P1 experience models: notifications, trip journal and saved collections."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class UserNotification(Base):
    __tablename__ = "user_notifications"
    __table_args__ = (UniqueConstraint("user_id", "dedupe_key", name="uq_user_notifications_dedupe"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    action_url: Mapped[str | None] = mapped_column(Text)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class TripJournalEntry(Base):
    __tablename__ = "trip_journal_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    activity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("activities.id", ondelete="SET NULL"), index=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text)
    photo_urls: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    actual_cost: Mapped[int | None] = mapped_column(Integer)
    rating: Mapped[int | None] = mapped_column(Integer)
    is_check_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class SavedTripCollection(Base):
    __tablename__ = "saved_trip_collections"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_saved_collections_user_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SavedTripCollectionItem(Base):
    __tablename__ = "saved_trip_collection_items"
    __table_args__ = (UniqueConstraint("collection_id", "publication_id", name="uq_collection_publication"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("saved_trip_collections.id", ondelete="CASCADE"), index=True)
    publication_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("public_trip_publications.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
