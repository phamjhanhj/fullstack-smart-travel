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
    POST /trips/{id}/days/generate - tu sinh day_plans dua vao start_date/end_date.
    overwrite=True: xoa toan bo day_plans cu (cascade activities) truoc khi tao lai.
    """
    if overwrite:
        existing = await db.execute(select(DayPlan).where(DayPlan.trip_id == trip.id))
        for day in existing.scalars().all():
            await db.delete(day)
        await db.flush()
    else:
        existing_count = await db.execute(select(DayPlan).where(DayPlan.trip_id == trip.id))
        if existing_count.scalars().first() is not None:
            raise AppError(
                "Chuyen di da co lich trinh, dung overwrite=true de tao lai", status_code=400
            )

    total_days = (trip.end_date - trip.start_date).days + 1
    new_days = [
        DayPlan(trip_id=trip.id, day_number=i, date=trip.start_date + timedelta(days=i - 1))
        for i in range(1, total_days + 1)
    ]
    db.add_all(new_days)
    await db.commit()

    for day in new_days:
        await db.refresh(day)

    return new_days
