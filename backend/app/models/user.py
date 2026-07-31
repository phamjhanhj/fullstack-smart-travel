"""ORM model — bảng users."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(39), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String, unique=True, nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    preferences_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_public_profile: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    accepts_tour_bookings: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    public_bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    public_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    public_zalo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    trips: Mapped[list["Trip"]] = relationship(back_populates="user", cascade="all, delete-orphan")
