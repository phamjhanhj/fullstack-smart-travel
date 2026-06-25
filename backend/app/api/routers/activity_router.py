"""
Router - Module 4: Day Plans & Activities (7 endpoints).
Chia 2 router con vi co endpoint long trip_id va co endpoint khong long
(PUT/DELETE /activities/{id}, PATCH /activities/reorder).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user, get_owned_trip
from app.core.response import envelope, envelope_created
from app.db.session import get_db
from app.models.trip import Trip
from app.models.user import User
from app.schemas.day_plan import (
    ActivityResponse,
    CreateActivityRequest,
    DayPlanBrief,
    DayPlanResponse,
    GenerateDaysRequest,
    ReorderActivitiesRequest,
    UpdateActivityRequest,
)
from app.services import activity_service
from sqlalchemy.ext.asyncio import AsyncSession

# --- Router long trong /trips/{trip_id} ---------------------------------------
trip_days_router = APIRouter(prefix="/trips/{trip_id}/days", tags=["Day Plans"])


@trip_days_router.get("")
async def list_days(
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
):
    days = await activity_service.list_days_with_activities(db, trip.id)
    return envelope(data=[DayPlanResponse.model_validate(d) for d in days])


@trip_days_router.get("/{day_id}")
async def get_day_detail(
    day_id: uuid.UUID,
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
):
    day_plan = await activity_service.get_day_or_404(db, trip.id, day_id)
    return envelope(data=DayPlanResponse.model_validate(day_plan))


@trip_days_router.post("/{day_id}/activities", status_code=201)
async def add_activity(
    day_id: uuid.UUID,
    payload: CreateActivityRequest,
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
):
    activity = await activity_service.create_activity(db, trip.id, day_id, payload)
    return envelope_created(
        data=ActivityResponse.model_validate(activity),
        message="Them hoat dong thanh cong",
    )


@trip_days_router.post("/generate", status_code=201)
async def generate_days(
    payload: GenerateDaysRequest,
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
):
    new_days = await activity_service.generate_day_plans(db, trip, payload.overwrite)
    return envelope_created(
        data=[DayPlanBrief.model_validate(d) for d in new_days],
        message=f"Da tao {len(new_days)} ngay cho chuyen di",
    )


# --- Router doc lap /activities/{id} (khong long trip_id) ----------------------
activities_router = APIRouter(prefix="/activities", tags=["Activities"])


@activities_router.put("/{activity_id}")
async def update_activity(
    activity_id: uuid.UUID,
    payload: UpdateActivityRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    activity = await activity_service.get_activity_owned_or_404(db, activity_id, current_user.id)
    updated = await activity_service.update_activity(db, activity, payload)
    return envelope(
        data=ActivityResponse.model_validate(updated),
        message="Cap nhat thanh cong",
    )


@activities_router.delete("/{activity_id}")
async def delete_activity(
    activity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    activity = await activity_service.get_activity_owned_or_404(db, activity_id, current_user.id)
    await activity_service.delete_activity(db, activity)
    return envelope(data=None, message="Da xoa hoat dong")


@activities_router.patch("/reorder")
async def reorder_activities(
    payload: ReorderActivitiesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await activity_service.reorder_activities(db, current_user.id, payload)
    return envelope(data=None, message="Da cap nhat thu tu")
