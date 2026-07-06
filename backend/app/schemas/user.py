"""Pydantic schemas — Module 2: Users (get/update profile)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    @field_validator("preferences_json", mode="before")
    @classmethod
    def validate_preferences_json(cls, value: Any) -> Any:
        if isinstance(value, str):
            import json
            try:
                return json.loads(value)
            except Exception:
                return None
        return value

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, value: str | None) -> str | None:
        if value is None or value.startswith(("http://", "https://", "/default-avatars/")):
            return value
        raise ValueError("avatar_url must be an http, https, or default avatar URL")
    created_at: datetime


class UpdateProfileRequest(BaseModel):
    """PATCH /users/me — toàn bộ field đều optional, chỉ update field được gửi lên."""
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    avatar_url: str | None = None
    preferences_json: UserPreferences | None = None

    @field_validator("preferences_json", mode="before")
    @classmethod
    def validate_preferences_json(cls, value: Any) -> Any:
        if isinstance(value, str):
            import json
            try:
                return json.loads(value)
            except Exception:
                return None
        return value
