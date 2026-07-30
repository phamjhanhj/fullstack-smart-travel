"""Pydantic schemas - Module 5: Locations (search, detail, nearby, upsert).
Backend dung OpenStreetMap (Nominatim + Overpass) thay cho Google Places.
"""
from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

LocationCategory = Literal["restaurant", "attraction", "hotel", "cafe", "other"]


class LocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    category: str | None = None
    google_place_id: str | None = None
    photo_url: str | None = None
    rating: float | None = None
    province_code: str | None = None
    province_name: str | None = None
    district: str | None = None
    ward: str | None = None
    subcategory: str | None = None
    typical_visit_minutes: int | None = None
    opening_hours: dict | None = None
    price: dict | None = None
    tags: list | None = None
    suitable_for: list | None = None
    data_confidence: str | None = None
    coordinate_status: str | None = None
    coordinate_accuracy_meters: int | None = None
    status: str | None = None
    result_source: Literal["dataset", "external"] | None = None


class ExploreLocationsResponse(BaseModel):
    items: list[LocationResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 36
    has_more: bool = False


class SupportedDestinationResponse(BaseModel):
    destination: str
    attraction_count: int = 0
    food_count: int = 0
    lodging_count: int = 0
    total_count: int = 0
    can_generate: bool = False


class NearbyLocationResponse(LocationResponse):
    """Ket qua tim kiem nearby co them khoang cach (met)."""
    distance_meters: int | None = None


class UpsertLocationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    category: LocationCategory | None = None
    google_place_id: str | None = None
    photo_url: str | None = None
    rating: float | None = Field(default=None, ge=0, le=5)

    @field_validator("photo_url")
    @classmethod
    def validate_photo_url(cls, value: str | None) -> str | None:
        if not value:
            return None
        if value.startswith(("http://", "https://", "/", "assets/")):
            return value
        return None


class UpsertLocationResponse(BaseModel):
    id: uuid.UUID
    name: str
    google_place_id: str | None = None
