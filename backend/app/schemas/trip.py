"""Pydantic schemas — Module 3: Trips (list, create, detail, update, delete, summary)."""
from __future__ import annotations

import uuid
import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.trip_share import ShareUserBrief, TripAccessRole, TripAccessType
from app.schemas.validators import TrimmedText, validated_http_url
from app.core.trip_limits import MAX_BUDGET_VND, MAX_TRAVELERS, MAX_TRIP_DURATION_DAYS

TripStatus = Literal["draft", "active", "completed"]


class CreateTripRequest(BaseModel):
    title: TrimmedText = Field(min_length=1, max_length=200)
    destination: TrimmedText = Field(min_length=1, max_length=200)
    start_date: dt.date
    end_date: dt.date
    budget: int | None = Field(default=None, ge=1, le=MAX_BUDGET_VND)
    num_travelers: int = Field(default=1, ge=1, le=MAX_TRAVELERS)
    preferences: str | None = Field(default=None, max_length=1500)

    @model_validator(mode="after")
    def validate_dates(self) -> "CreateTripRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date phai lon hon hoac bang start_date")
        duration_days = (self.end_date - self.start_date).days + 1
        if duration_days not in range(1, MAX_TRIP_DURATION_DAYS + 1):
            raise ValueError('TRIP_DURATION_TOO_LONG')
        return self


class UpdateTripRequest(BaseModel):
    """PUT /trips/{id} - toan bo field optional, chi update field duoc gui len."""
    title: TrimmedText | None = Field(default=None, min_length=1, max_length=200)
    destination: TrimmedText | None = Field(default=None, min_length=1, max_length=200)
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    budget: int | None = Field(default=None, ge=1, le=MAX_BUDGET_VND)
    num_travelers: int | None = Field(default=None, ge=1, le=MAX_TRAVELERS)
    preferences: str | None = Field(default=None, max_length=1500)
    status: TripStatus | None = None
    cover_image_url: str | None = Field(default=None, max_length=2048)

    @field_validator("cover_image_url")
    @classmethod
    def validate_cover_image_url(cls, value: str | None) -> str | None:
        return validated_http_url(value, "cover_image_url must be an http or https URL")

    @model_validator(mode="after")
    def validate_dates_when_both_are_present(self) -> "UpdateTripRequest":
        if self.start_date is not None and self.end_date is not None:
            duration_days = (self.end_date - self.start_date).days + 1
            if duration_days not in range(1, MAX_TRIP_DURATION_DAYS + 1):
                raise ValueError('TRIP_DURATION_TOO_LONG')
        if self.start_date is not None and self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date phai lon hon hoac bang start_date")
        return self


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
    owner: ShareUserBrief
    access_type: TripAccessType
    role: TripAccessRole


class DayPlanSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    day_number: int
    date: dt.date
    activities_count: int = 0


class TripDetailResponse(TripResponse):
    """GET /trips/{id} - kem danh sach ngay tom tat."""
    day_plans: list[DayPlanSummary] = Field(default_factory=list)


class TripPublicationSummary(BaseModel):
    id: uuid.UUID
    slug: str
    status: str
    published_at: dt.datetime | None = None
    view_count: int = 0
    save_count: int = 0
    clone_count: int = 0

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
    owner: ShareUserBrief
    access_type: TripAccessType
    role: TripAccessRole
    publication: TripPublicationSummary | None = None


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
