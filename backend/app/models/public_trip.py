"""Public, author-confirmed trip publications and reuse provenance."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class PublicTripPublication(Base):
    __tablename__ = "public_trip_publications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_trip_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="SET NULL"), nullable=True, index=True
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(240), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    destination: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    province_name: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    cover_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="public")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    moderation_status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    travel_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    travel_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    traveler_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    pace: Mapped[str | None] = mapped_column(String(30), nullable=True)
    budget_style: Mapped[str | None] = mapped_column(String(30), nullable=True)
    actual_total_cost: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actual_cost_per_person: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="VND")
    cost_is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    itinerary_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    place_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_rating: Mapped[float | None] = mapped_column(Numeric(2, 1), nullable=True)
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    privacy_options: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    allow_clone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_partial_import: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_comments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    save_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clone_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    author_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    author: Mapped["User"] = relationship(foreign_keys=[author_user_id])


class PublicTripSave(Base):
    __tablename__ = "public_trip_saves"
    __table_args__ = (
        UniqueConstraint("publication_id", "user_id", name="uq_public_trip_saves_publication_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public_trip_publications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PublicTripImport(Base):
    __tablename__ = "public_trip_imports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public_trip_publications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    import_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    source_day_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_activity_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    target_day_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("day_plans.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ActivityPublicationSource(Base):
    __tablename__ = "activity_publication_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("public_trip_publications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_activity_key: Mapped[str] = mapped_column(String(80), nullable=False)
    imported_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    author_verdict: Mapped[str | None] = mapped_column(String(30), nullable=True)
    author_note_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


from app.models.user import User  # noqa: E402
