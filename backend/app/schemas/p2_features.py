from __future__ import annotations
import re
import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field
from app.schemas.validators import TrimmedText

class CommentCreate(BaseModel): content: TrimmedText = Field(min_length=2, max_length=2000)
class RatingCreate(BaseModel): rating: int = Field(ge=1, le=5)
class CommentResponse(BaseModel):
    id: uuid.UUID; content: str; is_verified_trip: bool; created_at: datetime
    user: dict
class CommunityFeedback(BaseModel):
    comments: list[CommentResponse]; rating_average: float | None = None; rating_count: int = 0; my_rating: int | None = None
class RecommendationItem(BaseModel):
    publication: dict; reason: str; score: int

class ReportCreate(BaseModel):
    reason: Literal["spam", "misleading", "unsafe", "harassment", "copyright", "other"]
    details: TrimmedText | None = Field(default=None, max_length=1000)


class BookingInquiryCreate(BaseModel):
    contact_name: TrimmedText = Field(min_length=2, max_length=100)
    contact_phone: str = Field(min_length=7, max_length=30)
    travelers: int = Field(default=1, ge=1, le=100)
    message: TrimmedText | None = Field(default=None, max_length=1500)

    @classmethod
    def _normalize_phone(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[+()\d\s.-]{7,30}", value) or len(re.sub(r"\D", "", value)) < 7:
            raise ValueError("So dien thoai khong hop le")
        return value

    from pydantic import field_validator
    _validate_phone = field_validator("contact_phone")(_normalize_phone)


class BookingInquiryStatusUpdate(BaseModel):
    status: Literal["new", "contacted", "closed"]
class ReportStatusUpdate(BaseModel):
    decision: Literal["uphold", "dismiss"]
