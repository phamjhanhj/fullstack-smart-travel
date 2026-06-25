"""Business logic - Module 6: Budget."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.budget import BudgetItem
from app.models.trip import Trip
from app.schemas.budget import (
    CategoryBudgetSummary,
    CreateBudgetItemRequest,
    UpdateBudgetItemRequest,
    category_label,
)
from app.services.trip_service import get_trip_summary


async def get_budget_summary(db: AsyncSession, trip: Trip) -> dict:
    """GET /trips/{id}/budget - tai su dung logic tinh tu trip_service, dinh dang lai theo spec budget."""
    summary = await get_trip_summary(db, trip)

    categories = [
        CategoryBudgetSummary(
            category=category,
            label=category_label(category),
            planned=brief.planned,
            actual=brief.actual,
            itinerary_planned=brief.itinerary_planned,
            items_count=summary["_items_count_by_category"].get(category, 0),
        )
        for category, brief in summary["by_category"].items()
    ]

    return {
        "trip_id": trip.id,
        "budget_total": trip.budget,
        "budget_planned": summary["budget_planned"],
        "budget_actual": summary["budget_actual"],
        "budget_remaining": summary["budget_remaining"],
        "budget_itinerary_planned": summary["budget_itinerary_planned"],
        "overspent": summary["overspent"],
        "categories": categories,
    }



async def list_budget_items(db: AsyncSession, trip_id: uuid.UUID, category: str | None) -> list[BudgetItem]:
    """GET /trips/{id}/budget/items - filter theo category (optional)."""
    query = select(BudgetItem).where(BudgetItem.trip_id == trip_id)
    if category:
        query = query.where(BudgetItem.category == category)

    result = await db.execute(query.order_by(BudgetItem.date.desc().nullslast(), BudgetItem.created_at.desc()))
    return list(result.scalars().all())


async def create_budget_item(db: AsyncSession, trip_id: uuid.UUID, payload: CreateBudgetItemRequest) -> BudgetItem:
    item = BudgetItem(trip_id=trip_id, **payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def get_budget_item_owned_or_404(db: AsyncSession, item_id: uuid.UUID, user_id: uuid.UUID) -> BudgetItem:
    """Lay budget_item + kiem tra quyen so huu qua chain item -> trip -> user."""
    result = await db.execute(
        select(BudgetItem)
        .join(Trip, BudgetItem.trip_id == Trip.id)
        .where(BudgetItem.id == item_id, Trip.user_id == user_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise NotFoundError("Khong tim thay khoan chi nay")
    return item


async def update_budget_item(db: AsyncSession, item: BudgetItem, payload: UpdateBudgetItemRequest) -> BudgetItem:
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    await db.commit()
    await db.refresh(item)
    return item


async def delete_budget_item(db: AsyncSession, item: BudgetItem) -> None:
    await db.delete(item)
    await db.commit()
