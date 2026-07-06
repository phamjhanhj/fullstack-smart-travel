"""Pydantic schemas - Module 4: Day Plans & Activities (7 endpoints)."""
from __future__ import annotations

import uuid
import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ActivityType = Literal["meal", "attraction", "hotel", "transport", "other"]
GeneratePace = Literal["relaxed", "balanced", "packed"]
GenerateBudgetMode = Literal["flexible_15"]
GenerateUserPlacePriority = Literal["balanced"]


class LocationBrief(BaseModel):
    """Location long trong activity response - chi cac field can hien thi UI."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    category: str | None = None
    photo_url: str | None = None
    rating: float | None = None


class ActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    day_plan_id: uuid.UUID
    title: str
    description: str | None = None
    type: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    estimated_cost: int | None = None
    order_index: int
    booking_url: str | None = None
    notes: str | None = None

    @field_validator("booking_url")
    @classmethod
    def validate_booking_url(cls, value: str | None) -> str | None:
        if value is None or value.startswith(("http://", "https://")):
            return value
        raise ValueError("booking_url must be an http or https URL")
    location_id: uuid.UUID | None = None
    location: LocationBrief | None = None
    updated_at: dt.datetime | None = None


class DayPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trip_id: uuid.UUID
    day_number: int
    date: dt.date
    activities: list[ActivityResponse] = Field(default_factory=list)


class CreateActivityRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    type: ActivityType = "other"
    location_id: uuid.UUID | None = None
    start_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    estimated_cost: int | None = Field(default=None, ge=0)
    order_index: int = 0
    booking_url: str | None = None
    notes: str | None = None

    @field_validator("booking_url")
    @classmethod
    def validate_booking_url(cls, value: str | None) -> str | None:
        if value is None or value.startswith(("http://", "https://")):
            return value
        raise ValueError("booking_url must be an http or https URL")


class UpdateActivityRequest(BaseModel):
    """PUT /activities/{id} - toan bo field optional."""
    title: str | None = None
    description: str | None = None
    type: ActivityType | None = None
    location_id: uuid.UUID | None = None
    start_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    estimated_cost: int | None = Field(default=None, ge=0)
    booking_url: str | None = None
    notes: str | None = None


class ReorderItem(BaseModel):
    id: uuid.UUID
    order_index: int = Field(ge=0)


class ReorderActivitiesRequest(BaseModel):
    day_plan_id: uuid.UUID
    items: list[ReorderItem] = Field(min_length=1)


class GenerateDaysRequest(BaseModel):
    overwrite: bool = False
    must_visit: list[str] = Field(default_factory=list, max_length=20)
    pace: GeneratePace = "balanced"
    budget_mode: GenerateBudgetMode = "flexible_15"
    prioritize_user_places: GenerateUserPlacePriority = "balanced"


class DayPlanBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    day_number: int
    date: dt.date


class ItineraryGenerationSummary(BaseModel):
    total_estimated_cost: int = 0
    budget_limit: int | None = None
    budget_used_percent: int | None = None
    included_user_places: list[str] = Field(default_factory=list)
    missing_user_places: list[str] = Field(default_factory=list)
    candidate_places_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class GenerateDaysResponse(BaseModel):
    days: list[DayPlanBrief]
    summary: ItineraryGenerationSummary
