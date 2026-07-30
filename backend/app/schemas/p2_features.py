from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, Field

class CommentCreate(BaseModel): content: str = Field(min_length=2, max_length=2000)
class RatingCreate(BaseModel): rating: int = Field(ge=1, le=5)
class CommentResponse(BaseModel):
    id: uuid.UUID; content: str; is_verified_trip: bool; created_at: datetime
    user: dict
class CommunityFeedback(BaseModel):
    comments: list[CommentResponse]; rating_average: float | None = None; rating_count: int = 0; my_rating: int | None = None
class RecommendationItem(BaseModel):
    publication: dict; reason: str; score: int
