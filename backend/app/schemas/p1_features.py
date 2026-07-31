from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


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
    photo_urls: list[str] = Field(default_factory=list, max_length=10)
    actual_cost: int | None = Field(default=None, ge=0)
    rating: int | None = Field(default=None, ge=1, le=5)
    is_check_in: bool = False
    is_shared: bool = False


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
    name: str = Field(min_length=1, max_length=100)
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
