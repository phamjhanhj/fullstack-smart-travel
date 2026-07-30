"""ORM model — bảng locations."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)  # restaurant|attraction|hotel|cafe|other
    google_place_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True, index=True)
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Grounded dataset metadata. google_place_id is kept for backwards
    # compatibility with the existing OSM/search integration.
    source_dataset_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_place_id: Mapped[str | None] = mapped_column(String, nullable=True)
    dataset_version: Mapped[str | None] = mapped_column(String, nullable=True)
    province_code: Mapped[str | None] = mapped_column(String, nullable=True)
    province_name: Mapped[str | None] = mapped_column(String, nullable=True)
    district: Mapped[str | None] = mapped_column(String, nullable=True)
    ward: Mapped[str | None] = mapped_column(String, nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_category: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    suitable_for: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    typical_visit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    opening_hours: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    price: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    contact: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    booking: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    constraints: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    verification: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    data_confidence: Mapped[str | None] = mapped_column(String, nullable=True)
    coordinate_status: Mapped[str | None] = mapped_column(String, nullable=True)
    coordinate_accuracy_meters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    activities: Mapped[list["Activity"]] = relationship(back_populates="location")
