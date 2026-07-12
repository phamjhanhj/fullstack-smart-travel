"""Pydantic schemas for trip history events."""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.trip_share import ShareUserBrief


class TripHistoryChange(BaseModel):
    field: str
    label: str
    before: Any = None
    after: Any = None


class TripHistoryEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trip_id: uuid.UUID
    actor: ShareUserBrief | None = None
    entity_type: str
    entity_id: uuid.UUID | None = None
    action: str
    summary: str
    changes: list[TripHistoryChange] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: dt.datetime


class TripHistoryListResponse(BaseModel):
    items: list[TripHistoryEventResponse]
    total: int
    page: int
    limit: int
