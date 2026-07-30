"""Pydantic schemas - Module 4: Day Plans & Activities (7 endpoints)."""
from __future__ import annotations

import uuid
import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ActivityType = Literal["meal", "attraction", "hotel", "transport", "other"]
GeneratePace = Literal["relaxed", "balanced", "packed"]
GenerateBudgetMode = Literal["strict", "flexible_15", "comfort"]
GenerateUserPlacePriority = Literal["balanced", "high"]
GenerateTransportMode = Literal["walking", "motorbike", "car", "taxi", "public_transport", "mixed"]


class MustVisitRequest(BaseModel):
    location_id: uuid.UUID | None = None
    name: str = Field(min_length=2, max_length=200)
    priority: Literal["required", "preferred"] = "required"
    preferred_day: int | None = Field(default=None, ge=1, le=31)
    preferred_time: Literal["morning", "afternoon", "evening", "any"] = "any"
    minimum_duration_minutes: int | None = Field(default=None, ge=15, le=480)


class UserRequestCoverageItem(BaseModel):
    request: str
    status: Literal["scheduled", "unresolved", "infeasible"]
    day: int | None = None
    start_time: str | None = None
    location_id: str | None = None


class UserRequestCoverage(BaseModel):
    required_total: int = 0
    scheduled_total: int = 0
    items: list[UserRequestCoverageItem] = Field(default_factory=list)


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
    data_confidence: str | None = None
    coordinate_status: str | None = None
    coordinate_accuracy_meters: int | None = None
    opening_hours: dict | None = None
    price: dict | None = None


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
    is_locked: bool = False

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
    is_locked: bool = False

    @field_validator("booking_url")
    @classmethod
    def validate_booking_url(cls, value: str | None) -> str | None:
        if value is None or value.startswith(("http://", "https://")):
            return value
        raise ValueError("booking_url must be an http or https URL")

    @model_validator(mode="after")
    def validate_time_range(self) -> "CreateActivityRequest":
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self


class UpdateActivityRequest(BaseModel):
    """PUT /activities/{id} - toan bo field optional."""
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    type: ActivityType | None = None
    location_id: uuid.UUID | None = None
    start_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    estimated_cost: int | None = Field(default=None, ge=0)
    booking_url: str | None = None
    notes: str | None = None
    is_locked: bool | None = None

    @field_validator("booking_url")
    @classmethod
    def validate_booking_url(cls, value: str | None) -> str | None:
        if value is None or value.startswith(("http://", "https://")):
            return value
        raise ValueError("booking_url must be an http or https URL")

    @model_validator(mode="after")
    def validate_time_range_when_both_are_present(self) -> "UpdateActivityRequest":
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self


class ReorderItem(BaseModel):
    id: uuid.UUID
    order_index: int = Field(ge=0)


class ReorderActivitiesRequest(BaseModel):
    day_plan_id: uuid.UUID
    items: list[ReorderItem] = Field(min_length=1)


class ItineraryIssue(BaseModel):
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    day_id: uuid.UUID
    activity_ids: list[uuid.UUID] = Field(default_factory=list)


class ItineraryQualityResponse(BaseModel):
    score: int = Field(ge=0, le=100)
    error_count: int = 0
    warning_count: int = 0
    issues: list[ItineraryIssue] = Field(default_factory=list)


class GenerateDaysRequest(BaseModel):
    overwrite: bool = False
    must_visit: list[str] = Field(default_factory=list, max_length=20)
    must_visit_items: list[MustVisitRequest] = Field(default_factory=list, max_length=20)
    avoid_places: list[str] = Field(default_factory=list, max_length=20)
    interest_weights: dict[str, int] = Field(default_factory=dict)
    pace: GeneratePace = "balanced"
    budget_mode: GenerateBudgetMode = "flexible_15"
    prioritize_user_places: GenerateUserPlacePriority = "balanced"
    transport_mode: GenerateTransportMode = "mixed"
    departure_location: str | None = Field(default=None, max_length=120)
    departure_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    estimated_travel_hours: float | None = Field(default=None, ge=0)
    arrival_transport: str | None = Field(default=None, max_length=80)
    daily_start_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    daily_end_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    dietary_notes: str | None = Field(default=None, max_length=500)
    mobility_notes: str | None = Field(default=None, max_length=500)
    user_notes: str | None = Field(default=None, max_length=1_500)
    accept_long_daily_travel: bool = False
    max_daily_travel_minutes: int = Field(default=240, ge=30, le=720)
    early_start_allowed: bool = False
    night_driving_allowed: bool = False
    ai: bool = True

    @field_validator("interest_weights")
    @classmethod
    def validate_interest_weights(cls, value: dict[str, int]) -> dict[str, int]:
        cleaned: dict[str, int] = {}
        for key, weight in value.items():
            clean_key = str(key).strip().lower()
            if not clean_key:
                continue
            cleaned[clean_key] = max(0, min(int(weight), 10))
        return cleaned


class DayPlanBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    day_number: int
    date: dt.date


class ItineraryGenerationSummary(BaseModel):
    generation_id: str | None = None
    total_estimated_cost: int = 0
    budget_limit: int | None = None
    budget_used_percent: int | None = None
    included_user_places: list[str] = Field(default_factory=list)
    missing_user_places: list[str] = Field(default_factory=list)
    candidate_places_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    data_version: str | None = None
    prompt_version: str = "grounded-v2"
    planning_mode: Literal["grounded_v2", "fallback", "manual"] = "grounded_v2"
    verified_activities_count: int = 0
    approximate_coordinate_count: int = 0
    route_provider: str = "haversine"
    route_validation_status: Literal["passed", "warning", "not_run"] = "not_run"
    confidence_score: int | None = Field(default=None, ge=0, le=100)
    destination_topology: str | None = None
    user_request_coverage: UserRequestCoverage = Field(default_factory=UserRequestCoverage)
    generation_timings_ms: dict[str, int] = Field(default_factory=dict)
    fallback_reason: str | None = None


class GenerateDaysResponse(BaseModel):
    days: list[DayPlanBrief]
    summary: ItineraryGenerationSummary
