"""
Router - Module 6: Budget (5 endpoints).
Chia 2 router con: long trip_id (summary, list, create) va doc lap (update/delete item).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_owned_trip
from app.core.response import envelope, envelope_created
from app.db.session import get_db
from app.models.trip import Trip
from app.models.user import User
from app.schemas.budget import (
    BudgetCategory,
    BudgetItemResponse,
    BudgetSummaryResponse,
    CreateBudgetItemRequest,
    UpdateBudgetItemRequest,
)
from app.services import budget_service

trip_budget_router = APIRouter(prefix="/trips/{trip_id}/budget", tags=["Budget"])


@trip_budget_router.get("")
async def get_budget_summary(
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
):
    summary = await budget_service.get_budget_summary(db, trip)
    return envelope(data=BudgetSummaryResponse(**summary))


@trip_budget_router.get("/items")
async def list_budget_items(
    category: BudgetCategory | None = Query(default=None),
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
):
    items = await budget_service.list_budget_items(db, trip.id, category)
    return envelope(data=[BudgetItemResponse.model_validate(i) for i in items])


@trip_budget_router.post("/items", status_code=201)
async def add_budget_item(
    payload: CreateBudgetItemRequest,
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
):
    item = await budget_service.create_budget_item(db, trip.id, payload)
    return envelope_created(
        data=BudgetItemResponse.model_validate(item),
        message="Them khoan chi thanh cong",
    )


budget_items_router = APIRouter(prefix="/budget/items", tags=["Budget"])


@budget_items_router.put("/{item_id}")
async def update_budget_item(
    item_id: uuid.UUID,
    payload: UpdateBudgetItemRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await budget_service.get_budget_item_owned_or_404(db, item_id, current_user.id)
    updated = await budget_service.update_budget_item(db, item, payload)
    return envelope(
        data=BudgetItemResponse.model_validate(updated),
        message="Cap nhat thanh cong",
    )


@budget_items_router.delete("/{item_id}")
async def delete_budget_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await budget_service.get_budget_item_owned_or_404(db, item_id, current_user.id)
    await budget_service.delete_budget_item(db, item)
    return envelope(data=None, message="Da xoa khoan chi")
