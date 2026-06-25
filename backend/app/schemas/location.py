"""Pydantic schemas - Module 5: Locations (search, detail, nearby, upsert).
Backend dung OpenStreetMap (Nominatim + Overpass) thay cho Google Places.
"""
from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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


class UpsertLocationResponse(BaseModel):
    id: uuid.UUID
    name: str
    google_place_id: str | None = None
