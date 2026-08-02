"""Pydantic schemas — Module 1: Auth (register, login, refresh, me)."""
from __future__ import annotations

import uuid
from datetime import datetime

from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.user import UserPreferences


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=39, pattern=r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?$")
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=100)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if len(cleaned) < 2:
            raise ValueError("full_name must contain at least 2 characters")
        return cleaned


class RegisterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str | None = None
    full_name: str
    avatar_url: str | None = None
    created_at: datetime
    email_verified_at: datetime | None = None


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class ResendVerificationRequest(BaseModel):
    login: str = Field(min_length=1, max_length=254)

    @field_validator("login", mode="before")
    @classmethod
    def normalize_login(cls, value: str) -> str:
        return value.strip().lower()


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("login", mode="before")
    @classmethod
    def normalize_login(cls, value: str) -> str:
        return value.strip().lower()


class LoginUserInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str | None = None
    full_name: str
    avatar_url: str | None = None
    is_admin: bool = False


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: LoginUserInfo


class RefreshRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=32, max_length=4096)


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str | None = None
    full_name: str
    avatar_url: str | None = None
    is_admin: bool = False
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
    created_at: datetime
    email_verified_at: datetime | None = None
