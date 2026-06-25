"""ORM models — bảng trips và day_plans."""
from __future__ import annotations

import uuid
from datetime import date as date_type, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    destination: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    end_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    budget: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_travelers: Mapped[int] = mapped_column(Integer, default=1)
    preferences: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="draft")  # draft | active | completed
    cover_image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="trips")
    day_plans: Mapped[list["DayPlan"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan", order_by="DayPlan.day_number"
    )
    chat_history: Mapped[list["ChatMessage"]] = relationship(back_populates="trip", cascade="all, delete-orphan")
    ai_suggestions: Mapped[list["AiSuggestion"]] = relationship(back_populates="trip", cascade="all, delete-orphan")
    budget_items: Mapped[list["BudgetItem"]] = relationship(back_populates="trip", cascade="all, delete-orphan")


class DayPlan(Base):
    __tablename__ = "day_plans"
    __table_args__ = (UniqueConstraint("trip_id", "day_number", name="uq_day_plans_trip_day"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("trips.id"), nullable=False)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[date_type] = mapped_column(Date, nullable=False)

    trip: Mapped["Trip"] = relationship(back_populates="day_plans")
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="day_plan", cascade="all, delete-orphan", order_by="Activity.order_index"
    )


# Import ở cuối để tránh circular import khi type checking
from app.models.user import User  # noqa: E402
from app.models.activity import Activity  # noqa: E402
from app.models.chat import ChatMessage, AiSuggestion  # noqa: E402
from app.models.budget import BudgetItem  # noqa: E402
