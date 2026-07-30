"""Pydantic schemas for trip sharing."""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

TripShareRole = Literal["viewer", "editor"]
TripAccessRole = Literal["owner", "viewer", "editor"]
TripAccessType = Literal["owner", "shared"]
TripInviteStatus = Literal["pending", "accepted", "revoked", "rejected"]


class ShareUserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str | None = None
    full_name: str
    avatar_url: str | None = None


class CreateTripInviteRequest(BaseModel):
    recipient: str | None = Field(default=None, max_length=254)
    # Kept for backward compatibility with older clients.
    email: EmailStr | None = None
    role: TripShareRole
    expires_in_days: int = Field(default=7, ge=1, le=30)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> str | None:
        return str(value).strip().lower() if value else None

    @field_validator("recipient", mode="before")
    @classmethod
    def normalize_recipient(cls, value: str | None) -> str | None:
        cleaned = str(value).strip().lower() if value else None
        return cleaned or None


class UpdateTripParticipantRequest(BaseModel):
    role: TripShareRole


class TripParticipantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trip_id: uuid.UUID
    role: TripShareRole
    user: ShareUserBrief
    invited_by: ShareUserBrief
    created_at: dt.datetime
    updated_at: dt.datetime | None = None


class TripInviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trip_id: uuid.UUID
    email: str | None = None
    role: TripShareRole
    status: TripInviteStatus
    invited_by: ShareUserBrief
    accepted_by: ShareUserBrief | None = None
    expires_at: dt.datetime
    created_at: dt.datetime
    updated_at: dt.datetime | None = None
    token: str | None = None
    accept_url: str | None = None
    email_sent: bool | None = None


class TripInviteTripBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    destination: str
    start_date: dt.date
    end_date: dt.date
    cover_image_url: str | None = None


class TripInviteNotificationResponse(TripInviteResponse):
    trip: TripInviteTripBrief


class TripSharesResponse(BaseModel):
    participants: list[TripParticipantResponse]
    invites: list[TripInviteResponse]


class AcceptTripInviteResponse(BaseModel):
    trip_id: uuid.UUID
    role: TripShareRole
