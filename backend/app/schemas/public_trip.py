from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AuthorVerdict = Literal["must_go", "recommended", "preference_based", "skip"]
ActualStatus = Literal["visited", "changed", "skipped", "planned_only"]
PublicationVisibility = Literal["public", "unlisted"]
ImportMode = Literal["full_trip", "day", "activity"]


class PublicActivityReviewRequest(BaseModel):
    activity_id: uuid.UUID
    actual_status: ActualStatus = "visited"
    author_verdict: AuthorVerdict = "recommended"
    rating: int | None = Field(default=None, ge=1, le=5)
    next_traveler_note: str | None = Field(default=None, max_length=1000)
    best_time: str | None = Field(default=None, max_length=100)
    actual_wait_minutes: int | None = Field(default=None, ge=0, le=1440)
    booking_required: bool | None = None
    actual_cost: int | None = Field(default=None, ge=0)


class UpsertPublicTripRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    summary: str = Field(min_length=10, max_length=2000)
    visibility: PublicationVisibility = "public"
    traveler_type: str | None = Field(default=None, max_length=40)
    pace: str | None = Field(default=None, max_length=30)
    budget_style: str | None = Field(default=None, max_length=30)
    actual_total_cost: int | None = Field(default=None, ge=0)
    itinerary_rating: int | None = Field(default=None, ge=1, le=5)
    cost_rating: int | None = Field(default=None, ge=1, le=5)
    place_rating: int | None = Field(default=None, ge=1, le=5)
    best_places: list[str] = Field(default_factory=list, max_length=20)
    best_foods: list[str] = Field(default_factory=list, max_length=20)
    would_change: str | None = Field(default=None, max_length=2000)
    general_tips: str | None = Field(default=None, max_length=3000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    show_travel_month: bool = True
    show_author_name: bool = True
    show_cost: bool = True
    allow_clone: bool = True
    allow_partial_import: bool = True
    allow_comments: bool = True
    activity_reviews: list[PublicActivityReviewRequest] = Field(default_factory=list, max_length=300)
    author_confirmed: bool = False


class PublicTripAuthor(BaseModel):
    id: uuid.UUID
    full_name: str
    avatar_url: str | None = None


class PublicTripResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    title: str
    summary: str
    destination: str
    province_name: str | None = None
    cover_image_url: str | None = None
    visibility: str
    status: str
    moderation_status: str
    duration_days: int
    travel_month: int | None = None
    travel_year: int | None = None
    traveler_type: str | None = None
    pace: str | None = None
    budget_style: str | None = None
    actual_total_cost: int | None = None
    actual_cost_per_person: int | None = None
    cost_is_verified: bool
    itinerary_rating: int | None = None
    cost_rating: int | None = None
    place_rating: int | None = None
    overall_rating: float | None = None
    snapshot_version: int
    snapshot_json: dict[str, Any]
    privacy_options: dict[str, Any]
    tags: list[str]
    allow_clone: bool
    allow_partial_import: bool
    allow_comments: bool
    view_count: int
    save_count: int
    clone_count: int
    author_confirmed_at: dt.datetime | None = None
    published_at: dt.datetime | None = None
    created_at: dt.datetime
    updated_at: dt.datetime | None = None
    author: PublicTripAuthor
    is_saved: bool = False


class PublicTripListItem(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    summary: str
    destination: str
    cover_image_url: str | None = None
    duration_days: int
    travel_month: int | None = None
    travel_year: int | None = None
    traveler_type: str | None = None
    actual_cost_per_person: int | None = None
    overall_rating: float | None = None
    save_count: int
    clone_count: int
    published_at: dt.datetime | None = None
    tags: list[str]
    author: PublicTripAuthor
    is_saved: bool = False


class PublicTripListResponse(BaseModel):
    items: list[PublicTripListItem]
    total: int
    page: int
    limit: int


class PublicationEligibilityResponse(BaseModel):
    eligible: bool
    blocking_reasons: list[dict[str, str]]
    warnings: list[dict[str, str]]
    completion: dict[str, int]


class PublicTripImportRequest(BaseModel):
    import_mode: ImportMode
    target_trip_id: uuid.UUID | None = None
    target_day_plan_id: uuid.UUID | None = None
    source_day_number: int | None = Field(default=None, ge=1)
    source_activity_ids: list[str] = Field(default_factory=list, max_length=50)
    start_date: dt.date | None = None
    title: str | None = Field(default=None, max_length=200)
    budget: int | None = Field(default=None, ge=0)
    num_travelers: int = Field(default=1, ge=1)
    conflict_strategy: Literal["append", "replace_optional", "smart_merge"] = "smart_merge"

    @model_validator(mode="after")
    def validate_import_target(self) -> "PublicTripImportRequest":
        if self.import_mode == "full_trip" and not self.start_date:
            raise ValueError("start_date is required for full_trip")
        if self.import_mode in {"day", "activity"} and not self.target_day_plan_id:
            raise ValueError("target_day_plan_id is required")
        if self.import_mode == "day" and not self.source_day_number:
            raise ValueError("source_day_number is required")
        if self.import_mode == "activity" and not self.source_activity_ids:
            raise ValueError("source_activity_ids is required")
        return self


class PublicTripImportPreviewResponse(BaseModel):
    can_import: bool
    items: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    estimated_added_cost: int
    requires_route_reoptimization: bool


class PublicTripImportResponse(BaseModel):
    trip_id: uuid.UUID
    day_plan_id: uuid.UUID | None = None
    imported_activities: int
    warnings: list[str]
