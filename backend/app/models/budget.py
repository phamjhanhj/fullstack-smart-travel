"""ORM model — bảng budget_items."""
from __future__ import annotations

import uuid
from datetime import date as date_type, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class BudgetItem(Base):
    __tablename__ = "budget_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("trips.id"), nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)  # food|transport|hotel|activity|other
    label: Mapped[str] = mapped_column(String, nullable=False)
    planned_amount: Mapped[int] = mapped_column(Integer, default=0)
    actual_amount: Mapped[int] = mapped_column(Integer, default=0)
    date: Mapped[date_type | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    trip: Mapped["Trip"] = relationship(back_populates="budget_items")
