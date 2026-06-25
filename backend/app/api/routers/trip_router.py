"""Router - Module 3: Trips (6 endpoints)."""
from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_owned_trip
from app.core.response import envelope, envelope_created
from app.db.session import get_db
from app.models.trip import Trip
from app.models.user import User
from app.schemas.trip import (
    CreateTripRequest,
    TripDetailResponse,
    TripListItem,
    TripListResponse,
    TripResponse,
    TripStatus,
    TripSummaryResponse,
    UpdateTripRequest,
)
from app.services import trip_service

router = APIRouter(prefix="/trips", tags=["Trips"])


@router.get("")
async def list_trips(
    status: TripStatus | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    trips, total = await trip_service.list_trips(db, current_user, status, page, limit)
    data = TripListResponse(
        items=[TripListItem.model_validate(t) for t in trips],
        total=total,
        page=page,
        limit=limit,
    )
    return envelope(data=data)


@router.post("", status_code=201)
async def create_trip(
    payload: CreateTripRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    trip = await trip_service.create_trip(db, current_user, payload)
    return envelope_created(
        data=TripResponse.model_validate(trip),
        message="Tao chuyen di thanh cong",
    )


@router.get("/{trip_id}")
async def get_trip_detail(
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
):
    trip_with_days = await trip_service.get_trip_with_days(db, trip.id)
    return envelope(data=TripDetailResponse.model_validate(trip_with_days))


@router.put("/{trip_id}")
async def update_trip(
    payload: UpdateTripRequest,
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
):
    updated_trip = await trip_service.update_trip(db, trip, payload)
    return envelope(
        data=TripResponse.model_validate(updated_trip),
        message="Cap nhat thanh cong",
    )


@router.delete("/{trip_id}")
async def delete_trip(
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
):
    await trip_service.delete_trip(db, trip)
    return envelope(data=None, message="Da xoa chuyen di")


@router.get("/{trip_id}/summary")
async def get_trip_summary(
    trip: Trip = Depends(get_owned_trip),
    db: AsyncSession = Depends(get_db),
):
    summary = await trip_service.get_trip_summary(db, trip)
    summary.pop("_items_count_by_category", None)
    return envelope(data=TripSummaryResponse(**summary))
