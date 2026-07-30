"""Business logic - Module 3: Trips."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.activity import Activity
from app.models.budget import BudgetItem
from app.models.trip import DayPlan, Trip
from app.models.trip_share import TripParticipant
from app.models.user import User
from app.core.exceptions import AppError
from app.schemas.trip import CategoryBudgetBrief, CreateTripRequest, UpdateTripRequest
from app.services.trip_share_service import attach_access
from app.services import trip_history_service


async def list_trips(
    db: AsyncSession,
    user: User,
    status: str | None,
    page: int,
    limit: int,
    scope: str = "owned",
) -> tuple[list[Trip], int]:
    """Danh sach chuyen di theo quyen truy cap cua user."""
    trips: list[Trip] = []

    if scope in {"owned", "all"}:
        owned_query = select(Trip).where(Trip.user_id == user.id).options(selectinload(Trip.user))
        if status:
            owned_query = owned_query.where(Trip.status == status)
        owned_result = await db.execute(owned_query)
        trips.extend(attach_access(trip, "owner") for trip in owned_result.scalars().all())

    if scope in {"shared", "all"}:
        shared_query = (
            select(Trip, TripParticipant.role)
            .join(TripParticipant, TripParticipant.trip_id == Trip.id)
            .where(TripParticipant.user_id == user.id)
            .options(selectinload(Trip.user))
        )
        if status:
            shared_query = shared_query.where(Trip.status == status)
        shared_result = await db.execute(shared_query)
        for trip, role in shared_result.all():
            trips.append(attach_access(trip, role))

    trips.sort(key=lambda trip: trip.created_at, reverse=True)
    total = len(trips)
    start = (page - 1) * limit
    return trips[start:start + limit], total


async def create_trip(db: AsyncSession, user: User, payload: CreateTripRequest) -> Trip:
    """Tao chuyen di moi voi status mac dinh = draft."""
    cover_image_url = None
    try:
        from app.services.destination_photo_service import get_destination_photos
        photo_result = await get_destination_photos(db, payload.destination, 1)
        photos = photo_result.get("photos") or []
        cover_image_url = photos[0] if photos else None
    except Exception:
        cover_image_url = None

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
        cover_image_url=cover_image_url,
    )
    db.add(trip)
    await db.flush()
    await trip_history_service.record_history_event(
        db,
        trip_id=trip.id,
        actor_user_id=user.id,
        entity_type="trip",
        entity_id=trip.id,
        action="created",
        summary=f"Da tao chuyen di \"{trip.title}\"",
        metadata={"title": trip.title, "destination": trip.destination},
    )
    await db.commit()
    await db.refresh(trip)
    return trip


async def get_trip_with_days(db: AsyncSession, trip_id: uuid.UUID) -> Trip:
    """
    Lay trip kem day_plans (eager load) + dem so activities moi ngay.
    Dung cho GET /trips/{id}.
    """
    result = await db.execute(
        select(Trip).where(Trip.id == trip_id).options(selectinload(Trip.day_plans), selectinload(Trip.user))
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


async def update_trip(db: AsyncSession, trip: Trip, payload: UpdateTripRequest, actor: User) -> Trip:
    """Cap nhat tung field duoc gui len (PUT nhung semantics giong PATCH theo spec)."""
    access_role = getattr(trip, "_access_role", "owner")
    access_type = getattr(trip, "_access_type", "owner" if access_role == "owner" else "shared")
    tracked_fields = list(trip_history_service.TRIP_FIELD_LABELS.keys())
    before = trip_history_service.snapshot_fields(trip, tracked_fields)
    update_data = payload.model_dump(exclude_unset=True)
    final_start_date = update_data.get("start_date", trip.start_date)
    final_end_date = update_data.get("end_date", trip.end_date)
    final_status = update_data.get("status", trip.status)
    if final_end_date < final_start_date:
        raise AppError("Ngày kết thúc phải lớn hơn hoặc bằng ngày bắt đầu.", status_code=422)
    if final_status == "completed" and final_end_date > date.today():
        raise AppError("Không thể hoàn thành chuyến đi khi ngày kết thúc vẫn ở tương lai.", status_code=422)
    destination_changed = "destination" in update_data and update_data["destination"] != trip.destination
    for field, value in update_data.items():
        setattr(trip, field, value)

    if destination_changed and not trip.cover_image_url:
        try:
            from app.services.destination_photo_service import get_destination_photos
            photo_result = await get_destination_photos(db, trip.destination, 1)
            photos = photo_result.get("photos") or []
            if photos:
                trip.cover_image_url = photos[0]
        except Exception:
            pass

    await db.flush()
    after = trip_history_service.snapshot_fields(trip, tracked_fields)
    changes = trip_history_service.diff_snapshots(
        before,
        after,
        trip_history_service.TRIP_FIELD_LABELS,
    )
    if changes:
        await trip_history_service.record_history_event(
            db,
            trip_id=trip.id,
            actor_user_id=actor.id,
            entity_type="trip",
            entity_id=trip.id,
            action="updated",
            summary=f"Da cap nhat thong tin chuyen di \"{trip.title}\"",
            changes=changes,
        )
    await db.commit()
    await db.refresh(trip)
    trip._access_role = access_role  # type: ignore[attr-defined]
    trip._access_type = access_type  # type: ignore[attr-defined]
    return trip


async def delete_trip(db: AsyncSession, trip: Trip, actor: User) -> None:
    """
    Xoa trip - cascade tu dong xoa day_plans/activities/chat_history/
    ai_suggestions/budget_items nho relationship cascade='all, delete-orphan'.
    """
    await trip_history_service.record_history_event(
        db,
        trip_id=trip.id,
        actor_user_id=actor.id,
        entity_type="trip",
        entity_id=trip.id,
        action="deleted",
        summary=f"Da xoa chuyen di \"{trip.title}\"",
        metadata={"title": trip.title, "destination": trip.destination},
    )
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
