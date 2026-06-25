"""Business logic - Module 3: Trips."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.activity import Activity
from app.models.budget import BudgetItem
from app.models.trip import DayPlan, Trip
from app.models.user import User
from app.schemas.trip import CategoryBudgetBrief, CreateTripRequest, UpdateTripRequest


async def list_trips(
    db: AsyncSession,
    user: User,
    status: str | None,
    page: int,
    limit: int,
) -> tuple[list[Trip], int]:
    """Danh sach chuyen di cua user, filter theo status, co phan trang."""
    base_query = select(Trip).where(Trip.user_id == user.id)
    count_query = select(func.count()).select_from(Trip).where(Trip.user_id == user.id)

    if status:
        base_query = base_query.where(Trip.status == status)
        count_query = count_query.where(Trip.status == status)

    total = (await db.execute(count_query)).scalar_one()

    result = await db.execute(
        base_query.order_by(Trip.created_at.desc()).offset((page - 1) * limit).limit(limit)
    )
    trips = list(result.scalars().all())

    return trips, total


async def create_trip(db: AsyncSession, user: User, payload: CreateTripRequest) -> Trip:
    """Tao chuyen di moi voi status mac dinh = draft."""
    trip = Trip(
        user_id=user.id,
        title=payload.title,
        destination=payload.destination,
        start_date=payload.start_date,
        end_date=payload.end_date,
        budget=payload.budget,
        num_travelers=payload.num_travelers,
        preferences=payload.preferences,
        status="draft",
    )
    db.add(trip)
    await db.commit()
    await db.refresh(trip)
    return trip


async def get_trip_with_days(db: AsyncSession, trip_id: uuid.UUID) -> Trip:
    """
    Lay trip kem day_plans (eager load) + dem so activities moi ngay.
    Dung cho GET /trips/{id}.
    """
    result = await db.execute(
        select(Trip).where(Trip.id == trip_id).options(selectinload(Trip.day_plans))
    )
    trip = result.scalar_one()

    # Dem activities cho moi day_plan (1 query rieng vi can group by)
    if trip.day_plans:
        day_ids = [dp.id for dp in trip.day_plans]
        count_result = await db.execute(
            select(Activity.day_plan_id, func.count(Activity.id))
            .where(Activity.day_plan_id.in_(day_ids))
            .group_by(Activity.day_plan_id)
        )
        counts = dict(count_result.all())
        for dp in trip.day_plans:
            dp.activities_count = counts.get(dp.id, 0)  # type: ignore[attr-defined]

    return trip


async def update_trip(db: AsyncSession, trip: Trip, payload: UpdateTripRequest) -> Trip:
    """Cap nhat tung field duoc gui len (PUT nhung semantics giong PATCH theo spec)."""
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(trip, field, value)

    await db.commit()
    await db.refresh(trip)
    return trip


async def delete_trip(db: AsyncSession, trip: Trip) -> None:
    """
    Xoa trip - cascade tu dong xoa day_plans/activities/chat_history/
    ai_suggestions/budget_items nho relationship cascade='all, delete-orphan'.
    """
    await db.delete(trip)
    await db.commit()


async def get_trip_summary(db: AsyncSession, trip: Trip) -> dict:
    """
    Tính tóm tắt: số ngày, số hoạt động, ngân sách planned/actual theo category.
    Đồng thời tính tổng chi phí ước tính từ lịch trình (estimated_cost của các activities).
    """
    total_days_result = await db.execute(
        select(func.count()).select_from(DayPlan).where(DayPlan.trip_id == trip.id)
    )
    total_days = total_days_result.scalar_one()

    total_activities_result = await db.execute(
        select(func.count())
        .select_from(Activity)
        .join(DayPlan, Activity.day_plan_id == DayPlan.id)
        .where(DayPlan.trip_id == trip.id)
    )
    total_activities = total_activities_result.scalar_one()

    # 1. Tính chi phí thực tế & dự kiến thủ công từ bảng budget_items
    category_result = await db.execute(
        select(
            BudgetItem.category,
            func.coalesce(func.sum(BudgetItem.planned_amount), 0),
            func.coalesce(func.sum(BudgetItem.actual_amount), 0),
            func.count(BudgetItem.id),
        )
        .where(BudgetItem.trip_id == trip.id)
        .group_by(BudgetItem.category)
    )
    rows = category_result.all()

    # 2. Tính chi phí ước tính từ lịch trình (activities)
    act_category_costs_result = await db.execute(
        select(
            Activity.type,
            func.coalesce(func.sum(Activity.estimated_cost), 0)
        )
        .join(DayPlan, Activity.day_plan_id == DayPlan.id)
        .where(DayPlan.trip_id == trip.id)
        .group_by(Activity.type)
    )
    act_costs = dict(act_category_costs_result.all())

    # Map activity types sang budget categories
    def map_type_to_category(act_type: str | None) -> str:
        if act_type == "meal":
            return "food"
        if act_type == "attraction":
            return "activity"
        if act_type in ["transport", "hotel", "other"]:
            return act_type
        return "other"

    itinerary_category_costs: dict[str, int] = {
        "food": 0,
        "transport": 0,
        "hotel": 0,
        "activity": 0,
        "other": 0
    }
    for act_type, cost in act_costs.items():
        cat = map_type_to_category(act_type)
        itinerary_category_costs[cat] += cost

    budget_itinerary_planned = sum(itinerary_category_costs.values())

    # Khởi tạo tất cả 5 categories mặc định để tránh thiếu trường ở Frontend
    categories_list = ["food", "transport", "hotel", "activity", "other"]
    by_category: dict[str, CategoryBudgetBrief] = {
        cat: CategoryBudgetBrief(planned=0, actual=0, itinerary_planned=0)
        for cat in categories_list
    }
    items_count_by_category: dict[str, int] = {cat: 0 for cat in categories_list}

    budget_planned = 0
    budget_actual = 0

    for category, planned, actual, items_count in rows:
        if category in by_category:
            by_category[category].planned = planned
            by_category[category].actual = actual
            items_count_by_category[category] = items_count
            budget_planned += planned
            budget_actual += actual

    # Cập nhật chi phí ước tính từ lịch trình vào từng category
    for cat, cost in itinerary_category_costs.items():
        if cat in by_category:
            by_category[cat].itinerary_planned = cost

    budget_total = trip.budget or 0
    budget_remaining = budget_total - budget_actual
    budget_used_percent = int(round((budget_actual / budget_total) * 100)) if budget_total > 0 else 0

    return {
        "trip_id": trip.id,
        "total_days": total_days,
        "total_activities": total_activities,
        "budget_total": trip.budget,
        "budget_planned": budget_planned,
        "budget_actual": budget_actual,
        "budget_remaining": budget_remaining,
        "budget_itinerary_planned": budget_itinerary_planned,
        "overspent": budget_actual > budget_total if budget_total > 0 else False,
        "budget_used_percent": budget_used_percent,
        "by_category": by_category,
        "_items_count_by_category": items_count_by_category,  # dùng nội bộ cho budget_service
    }

