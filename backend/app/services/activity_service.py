"""Business logic - Module 4: Day Plans & Activities."""
from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.models.activity import Activity
from app.models.trip import DayPlan, Trip
from app.schemas.day_plan import CreateActivityRequest, ReorderActivitiesRequest, UpdateActivityRequest


async def list_days_with_activities(db: AsyncSession, trip_id: uuid.UUID) -> list[DayPlan]:
    """GET /trips/{id}/days - toan bo ngay kem activities long nhau, sap theo day_number."""
    result = await db.execute(
        select(DayPlan)
        .where(DayPlan.trip_id == trip_id)
        .options(selectinload(DayPlan.activities).selectinload(Activity.location))
        .order_by(DayPlan.day_number)
    )
    return list(result.scalars().all())


async def get_day_or_404(db: AsyncSession, trip_id: uuid.UUID, day_id: uuid.UUID) -> DayPlan:
    """GET /trips/{id}/days/{day_id} - kiem tra day thuoc dung trip."""
    result = await db.execute(
        select(DayPlan)
        .where(DayPlan.id == day_id, DayPlan.trip_id == trip_id)
        .options(selectinload(DayPlan.activities))
    )
    day_plan = result.scalar_one_or_none()
    if day_plan is None:
        raise NotFoundError("Khong tim thay ngay nay trong chuyen di")
    return day_plan


async def create_activity(
    db: AsyncSession, trip_id: uuid.UUID, day_id: uuid.UUID, payload: CreateActivityRequest
) -> Activity:
    """POST /trips/{id}/days/{day_id}/activities."""
    await get_day_or_404(db, trip_id, day_id)  # dam bao day thuoc dung trip

    activity = Activity(day_plan_id=day_id, **payload.model_dump())
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    return activity


async def get_activity_owned_or_404(db: AsyncSession, activity_id: uuid.UUID, user_id: uuid.UUID) -> Activity:
    """
    Lay activity + kiem tra quyen so huu thong qua chain activity -> day_plan -> trip -> user.
    Dung cho PUT/DELETE /activities/{id} (path khong co trip_id).
    """
    result = await db.execute(
        select(Activity)
        .join(DayPlan, Activity.day_plan_id == DayPlan.id)
        .join(Trip, DayPlan.trip_id == Trip.id)
        .where(Activity.id == activity_id, Trip.user_id == user_id)
    )
    activity = result.scalar_one_or_none()
    if activity is None:
        raise NotFoundError("Khong tim thay hoat dong nay")
    return activity


async def update_activity(db: AsyncSession, activity: Activity, payload: UpdateActivityRequest) -> Activity:
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(activity, field, value)

    await db.commit()
    await db.refresh(activity)
    return activity


async def delete_activity(db: AsyncSession, activity: Activity) -> None:
    await db.delete(activity)
    await db.commit()


async def reorder_activities(db: AsyncSession, user_id: uuid.UUID, payload: ReorderActivitiesRequest) -> None:
    """
    PATCH /activities/reorder - cap nhat order_index hang loat.
    Kiem tra day_plan_id thuoc trip cua user truoc khi update bat ky activity nao.
    """
    day_result = await db.execute(
        select(DayPlan).join(Trip, DayPlan.trip_id == Trip.id).where(
            DayPlan.id == payload.day_plan_id, Trip.user_id == user_id
        )
    )
    if day_result.scalar_one_or_none() is None:
        raise ForbiddenError("Ban khong co quyen sap xep ngay nay")

    activity_ids = [item.id for item in payload.items]
    result = await db.execute(
        select(Activity).where(Activity.id.in_(activity_ids), Activity.day_plan_id == payload.day_plan_id)
    )
    activities_by_id = {a.id: a for a in result.scalars().all()}

    if len(activities_by_id) != len(activity_ids):
        raise AppError("Mot so hoat dong khong thuoc ngay nay", status_code=400)

    for item in payload.items:
        activities_by_id[item.id].order_index = item.order_index

    await db.commit()


async def generate_day_plans(db: AsyncSession, trip: Trip, overwrite: bool) -> list[DayPlan]:
    """
    POST /trips/{id}/days/generate - Tự động lập lịch trình bằng AI (Groq/Llama 3).
    overwrite=True: xóa toàn bộ day_plans cũ trước khi tạo lại.
    """
    # 1. Gọi AI lập lịch trình trước khi chỉnh sửa DB
    from app.services.ai_service import generate_itinerary_with_ai
    itinerary_data = await generate_itinerary_with_ai(trip)

    # 2. Xử lý xóa lịch trình cũ nếu overwrite
    if overwrite:
        existing = await db.execute(select(DayPlan).where(DayPlan.trip_id == trip.id))
        for day in existing.scalars().all():
            await db.delete(day)
        await db.flush()
    else:
        existing_count = await db.execute(select(DayPlan).where(DayPlan.trip_id == trip.id))
        if existing_count.scalars().first() is not None:
            raise AppError(
                "Chuyến đi đã có lịch trình, dùng overwrite=true để tạo lại", status_code=400
            )

    # 3. Tạo các ngày (day_plans) mới
    total_days = (trip.end_date - trip.start_date).days + 1
    new_days = [
        DayPlan(trip_id=trip.id, day_number=i, date=trip.start_date + timedelta(days=i - 1))
        for i in range(1, total_days + 1)
    ]
    db.add_all(new_days)
    await db.flush()  # Lấy ID của các ngày để liên kết hoạt động

    # Map số ngày sang object để gán hoạt động
    day_map = {day.day_number: day for day in new_days}

    # 4. Parse và lưu hoạt động do AI trả về
    import re

    def sanitize_time(time_str) -> str | None:
        if not isinstance(time_str, str):
            return None
        time_str = time_str.strip()
        if re.match(r"^([01]\d|2[0-3]):[0-5]\d$", time_str):
            return time_str
        if re.match(r"^\d:[0-5]\d$", time_str):
            return f"0{time_str}"
        return None

    def sanitize_type(type_str) -> str:
        if type_str in ["meal", "attraction", "hotel", "transport", "other"]:
            return type_str
        return "other"

    def sanitize_cost(cost) -> int | None:
        if cost is None:
            return None
        try:
            val = int(cost)
            return val if val >= 0 else None
        except (ValueError, TypeError):
            return None

    days_list = itinerary_data.get("days", [])
    if not isinstance(days_list, list):
        days_list = []

    for ai_day in days_list:
        if not isinstance(ai_day, dict):
            continue
        day_num = ai_day.get("day_number")
        day_plan = day_map.get(day_num)
        if not day_plan:
            continue

        activities_list = ai_day.get("activities", [])
        if not isinstance(activities_list, list):
            continue

        for idx, act_data in enumerate(activities_list):
            if not isinstance(act_data, dict):
                continue

            title = act_data.get("title", "Hoạt động").strip()
            if not title:
                title = "Hoạt động"
            title = title[:200]

            activity = Activity(
                day_plan_id=day_plan.id,
                title=title,
                description=act_data.get("description"),
                type=sanitize_type(act_data.get("type")),
                start_time=sanitize_time(act_data.get("start_time")),
                end_time=sanitize_time(act_data.get("end_time")),
                estimated_cost=sanitize_cost(act_data.get("estimated_cost")),
                notes=act_data.get("notes"),
                order_index=idx,
            )
            db.add(activity)

    await db.commit()

    for day in new_days:
        await db.refresh(day)

    return new_days

