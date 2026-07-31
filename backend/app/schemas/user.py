"""Pydantic schemas — Module 2: Users (get/update profile)."""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserPreferences(BaseModel):
    """Cấu trúc preferences_json lưu trong bảng users."""
    travel_style: Literal["budget", "mid-range", "luxury"] | None = None
    interests: list[str] = Field(default_factory=list)
    budget_range: Literal["low", "medium", "high"] | None = None


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str | None = None
    full_name: str
    avatar_url: str | None = None
    preferences_json: UserPreferences | None = None
    is_public_profile: bool = False
    accepts_tour_bookings: bool = False
    public_bio: str | None = None
    public_phone: str | None = None
    public_zalo_url: str | None = None

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
    is_public_profile: bool | None = None
    accepts_tour_bookings: bool | None = None
    public_bio: str | None = Field(default=None, max_length=1000)
    public_phone: str | None = Field(default=None, max_length=30)
    public_zalo_url: str | None = Field(default=None, max_length=500)

    @field_validator("public_phone")
    @classmethod
    def validate_public_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if not re.fullmatch(r"[+()\d\s.-]{7,30}", value) or len(re.sub(r"\D", "", value)) < 7:
            raise ValueError("So dien thoai cong khai khong hop le")
        return value

    @field_validator("public_zalo_url")
    @classmethod
    def validate_public_zalo_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        parsed = urlparse(value)
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in {"zalo.me", "www.zalo.me", "chat.zalo.me"}:
            raise ValueError("Lien ket Zalo phai dung HTTPS va thuoc zalo.me")
        return value
    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, value: str | None) -> str | None:
        if value is None or value.startswith(("http://", "https://", "/default-avatars/")):
            return value
        raise ValueError("avatar_url must be an http, https, or default avatar URL")

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


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)

class PublicUserProfileResponse(BaseModel):
    id: uuid.UUID
    username: str
    full_name: str
    avatar_url: str | None = None
    public_bio: str | None = None
    public_phone: str | None = None
    public_zalo_url: str | None = None
    accepts_tour_bookings: bool = False
    public_trips: list[dict[str, Any]] = Field(default_factory=list)