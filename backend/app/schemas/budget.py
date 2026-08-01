"""Pydantic schemas - Module 6: Budget (summary, items CRUD)."""
from __future__ import annotations

import uuid
import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from app.core.trip_limits import MAX_BUDGET_VND
from app.schemas.validators import ParticipantText, TrimmedText

BudgetCategory = Literal["food", "transport", "hotel", "activity", "other"]

_CATEGORY_LABELS: dict[str, str] = {
    "food": "An uong",
    "transport": "Di chuyen",
    "hotel": "Luu tru",
    "activity": "Hoat dong tham quan",
    "other": "Khac",
}


class BudgetItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trip_id: uuid.UUID
    category: str
    label: str
    planned_amount: int
    actual_amount: int
    date: dt.date | None = None
    paid_by: str | None = None
    participants: list[str] | None = None
    created_at: dt.datetime
    updated_at: dt.datetime | None = None


class CreateBudgetItemRequest(BaseModel):
    category: BudgetCategory
    label: TrimmedText = Field(min_length=1, max_length=200)
    planned_amount: int = Field(default=0, ge=0, le=MAX_BUDGET_VND)
    actual_amount: int = Field(default=0, ge=0, le=MAX_BUDGET_VND)
    date: dt.date | None = None
    paid_by: TrimmedText | None = Field(default=None, max_length=100)
    participants: list[ParticipantText] | None = Field(default=None, max_length=100)


class UpdateBudgetItemRequest(BaseModel):
    """PUT /budget/items/{id} - toan bo field optional."""
    category: BudgetCategory | None = None
    label: TrimmedText | None = Field(default=None, min_length=1, max_length=200)
    planned_amount: int | None = Field(default=None, ge=0, le=MAX_BUDGET_VND)
    actual_amount: int | None = Field(default=None, ge=0, le=MAX_BUDGET_VND)
    date: dt.date | None = None
    paid_by: TrimmedText | None = Field(default=None, max_length=100)
    participants: list[ParticipantText] | None = Field(default=None, max_length=100)


class CategoryBudgetSummary(BaseModel):
    category: str
    label: str
    planned: int
    actual: int
    itinerary_planned: int = 0
    items_count: int


class BudgetSummaryResponse(BaseModel):
    trip_id: uuid.UUID
    budget_total: int | None
    budget_planned: int
    budget_actual: int
    budget_remaining: int
    budget_itinerary_planned: int = 0
    overspent: bool
    categories: list[CategoryBudgetSummary]



def category_label(category: str) -> str:
    return _CATEGORY_LABELS.get(category, category)
