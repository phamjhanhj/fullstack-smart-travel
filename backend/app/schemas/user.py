"""Pydantic schemas — Module 2: Users (get/update profile)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserPreferences(BaseModel):
    """Cấu trúc preferences_json lưu trong bảng users."""
    travel_style: Literal["budget", "mid-range", "luxury"] | None = None
    interests: list[str] = Field(default_factory=list)
    budget_range: Literal["low", "medium", "high"] | None = None


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    avatar_url: str | None = None
    preferences_json: UserPreferences | None = None
    created_at: datetime


class UpdateProfileRequest(BaseModel):
    """PATCH /users/me — toàn bộ field đều optional, chỉ update field được gửi lên."""
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    avatar_url: str | None = None
    preferences_json: UserPreferences | None = None
