"""Pydantic schemas - Module 7: AI Chat & Suggestions (4 endpoints)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ChatRole = Literal["user", "assistant"]
SuggestionType = Literal["itinerary", "place", "budget"]
SuggestionStatus = Literal["pending", "accepted", "rejected"]


class SendMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    stream: bool = False


class ChatMessageResponse(BaseModel):
    """Response cho truong hop stream=false."""
    message_id: uuid.UUID
    role: str = "assistant"
    message: str
    suggestion_id: uuid.UUID | None = None
    created_at: datetime


class ChatHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    message: str
    created_at: datetime


class AiSuggestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trip_id: uuid.UUID
    type: str
    status: str
    content_json: dict[str, Any]
    created_at: datetime


class UpdateSuggestionStatusRequest(BaseModel):
    status: Literal["accepted", "rejected"]


class UpdateSuggestionStatusResponse(BaseModel):
    suggestion_id: uuid.UUID
    status: str
    activities_created: int = 0
