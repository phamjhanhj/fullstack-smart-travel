from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.trip_limits import MAX_BUDGET_VND
from app.schemas.validators import PhotoUrlText, TrimmedText, validated_http_url


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    type: str
    title: str
    message: str
    action_url: str | None = None
    payload_json: dict = Field(default_factory=dict)
    read_at: datetime | None = None
    created_at: datetime


class JournalCreate(BaseModel):
    activity_id: uuid.UUID | None = None
    entry_date: date
    note: str | None = Field(default=None, max_length=3000)
    photo_urls: list[PhotoUrlText] = Field(default_factory=list, max_length=10)
    actual_cost: int | None = Field(default=None, ge=0, le=MAX_BUDGET_VND)
    rating: int | None = Field(default=None, ge=1, le=5)
    is_check_in: bool = False
    is_shared: bool = False

    @field_validator("photo_urls")
    @classmethod
    def validate_photo_urls(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            if len(value) > 2048:
                raise ValueError("photo_urls must contain only http or https URLs")
            url = validated_http_url(value, "photo_urls must contain only http or https URLs")
            assert url is not None
            cleaned.append(url)
        return cleaned


class JournalVisibilityUpdate(BaseModel):
    is_shared: bool


class JournalResponse(JournalCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    trip_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime | None = None


class CollectionCreate(BaseModel):
    name: TrimmedText = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class CollectionResponse(CollectionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    item_count: int = 0


class EmergencyPreviewRequest(BaseModel):
    reason: Literal["rain", "closed", "late", "skip", "other"]
    activity_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=500)


class EmergencyOption(BaseModel):
    id: str
    title: str
    description: str
    impact: str
    requires_confirmation: bool = True
