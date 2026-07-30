"""Router - Module 3: Trips (6 endpoints)."""
from __future__ import annotations

import math
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_trip_edit_access, get_trip_owner_access, get_trip_read_access
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
from app.schemas.trip_history import TripHistoryEventResponse, TripHistoryListResponse
from app.services import public_trip_service, trip_service
from app.services import trip_history_service

router = APIRouter(prefix="/trips", tags=["Trips"])


def _trip_access_payload(trip: Trip, owner: User | None = None) -> dict:
    owner_user = owner or trip.user
    role = getattr(trip, "_access_role", "owner")
    access_type = getattr(trip, "_access_type", "owner" if role == "owner" else "shared")
    return {
        "id": trip.id,
        "title": trip.title,
        "destination": trip.destination,
        "start_date": trip.start_date,
        "end_date": trip.end_date,
        "budget": trip.budget,
        "num_travelers": trip.num_travelers,
        "status": trip.status,
        "preferences": trip.preferences,
        "cover_image_url": trip.cover_image_url,
        "created_at": trip.created_at,
        "updated_at": trip.updated_at,
        "owner": owner_user,
        "access_type": access_type,
        "role": role,
    }


def _trip_detail_payload(trip: Trip, owner: User | None = None) -> dict:
    data = _trip_access_payload(trip, owner)
    data["day_plans"] = getattr(trip, "day_plans", [])
    return data


@router.get("")
async def list_trips(
    status: TripStatus | None = Query(default=None),
    scope: Literal["owned", "shared", "all"] = Query(default="owned"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    trips, total = await trip_service.list_trips(db, current_user, status, page, limit, scope)
    publications = await public_trip_service.publication_summaries_by_trip_ids(
        db, [trip.id for trip in trips if getattr(trip, "_access_type", "owner") == "owner"]
    )
    items = []
    for trip in trips:
        payload = _trip_access_payload(trip)
        publication = publications.get(trip.id)
        if publication:
            payload["publication"] = {
                "id": publication.id,
                "slug": publication.slug,
                "status": publication.status,
                "published_at": publication.published_at,
                "view_count": publication.view_count,
                "save_count": publication.save_count,
                "clone_count": publication.clone_count,
            }
        items.append(TripListItem.model_validate(payload))
    data = TripListResponse(
        items=items,
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
        data=TripResponse.model_validate(_trip_access_payload(trip, current_user)),
        message="Tao chuyen di thanh cong",
    )


@router.get("/{trip_id}")
async def get_trip_detail(
    trip: Trip = Depends(get_trip_read_access),
    db: AsyncSession = Depends(get_db),
):
    role = getattr(trip, "_access_role", "owner")
    trip_with_days = await trip_service.get_trip_with_days(db, trip.id)
    trip_with_days._access_role = role  # type: ignore[attr-defined]
    trip_with_days._access_type = "owner" if role == "owner" else "shared"  # type: ignore[attr-defined]
    return envelope(data=TripDetailResponse.model_validate(_trip_detail_payload(trip_with_days)))


@router.put("/{trip_id}")
async def update_trip(
    payload: UpdateTripRequest,
    trip: Trip = Depends(get_trip_edit_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    updated_trip = await trip_service.update_trip(db, trip, payload, current_user)
    return envelope(
        data=TripResponse.model_validate(_trip_access_payload(updated_trip)),
        message="Cap nhat thanh cong",
    )


@router.delete("/{trip_id}")
async def delete_trip(
    trip: Trip = Depends(get_trip_owner_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await trip_service.delete_trip(db, trip, current_user)
    return envelope(data=None, message="Da xoa chuyen di")


@router.get("/{trip_id}/summary")
async def get_trip_summary(
    trip: Trip = Depends(get_trip_read_access),
    db: AsyncSession = Depends(get_db),
):
    summary = await trip_service.get_trip_summary(db, trip)
    summary.pop("_items_count_by_category", None)
    return envelope(data=TripSummaryResponse(**summary))


@router.get("/{trip_id}/history")
async def get_trip_history(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=30, ge=1, le=100),
    entity_type: str | None = Query(default=None),
    action: str | None = Query(default=None),
    trip: Trip = Depends(get_trip_read_access),
    db: AsyncSession = Depends(get_db),
):
    events, total = await trip_history_service.list_history_events(
        db,
        trip.id,
        page=page,
        limit=limit,
        entity_type=entity_type,
        action=action,
    )
    data = TripHistoryListResponse(
        items=[
            TripHistoryEventResponse.model_validate(trip_history_service.history_event_payload(event))
            for event in events
        ],
        total=total,
        page=page,
        limit=limit,
    )
    return envelope(data=data)
