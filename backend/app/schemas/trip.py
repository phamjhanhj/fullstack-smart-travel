"""Pydantic schemas — Module 3: Trips (list, create, detail, update, delete, summary)."""
from __future__ import annotations

import uuid
import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TripStatus = Literal["draft", "active", "completed"]


class CreateTripRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    destination: str = Field(min_length=1, max_length=200)
    start_date: dt.date
    end_date: dt.date
    budget: int | None = Field(default=None, ge=0)
    num_travelers: int = Field(default=1, ge=1)
    preferences: str | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "CreateTripRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date phai lon hon hoac bang start_date")
        return self


class UpdateTripRequest(BaseModel):
    """PUT /trips/{id} - toan bo field optional, chi update field duoc gui len."""
    title: str | None = None
    destination: str | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    budget: int | None = Field(default=None, ge=0)
    num_travelers: int | None = Field(default=None, ge=1)
    preferences: str | None = None
    status: TripStatus | None = None
    cover_image_url: str | None = None


class TripResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    destination: str
    start_date: dt.date
    end_date: dt.date
    budget: int | None = None
    num_travelers: int
    status: str
    preferences: str | None = None
    cover_image_url: str | None = None
    created_at: dt.datetime
    updated_at: dt.datetime | None = None


class DayPlanSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    day_number: int
    date: dt.date
    activities_count: int = 0


class TripDetailResponse(TripResponse):
    """GET /trips/{id} - kem danh sach ngay tom tat."""
    day_plans: list[DayPlanSummary] = Field(default_factory=list)


class TripListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    destination: str
    start_date: dt.date
    end_date: dt.date
    budget: int | None = None
    num_travelers: int
    status: str
    cover_image_url: str | None = None
    created_at: dt.datetime


class TripListResponse(BaseModel):
    items: list[TripListItem]
    total: int
    page: int
    limit: int


class CategoryBudgetBrief(BaseModel):
    planned: int = 0
    actual: int = 0
    itinerary_planned: int = 0


class TripSummaryResponse(BaseModel):
    trip_id: uuid.UUID
    total_days: int
    total_activities: int
    budget_total: int | None
    budget_planned: int
    budget_actual: int
    budget_remaining: int
    budget_itinerary_planned: int = 0
    overspent: bool
    budget_used_percent: int
    by_category: dict[str, CategoryBudgetBrief]

