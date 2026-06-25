"""Router - Module 5: Locations (4 endpoints)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import envelope, envelope_created
from app.db.session import get_db
from app.models.user import User
from app.schemas.location import (
    LocationCategory,
    LocationResponse,
    NearbyLocationResponse,
    UpsertLocationRequest,
    UpsertLocationResponse,
)
from app.services import location_service

router = APIRouter(prefix="/locations", tags=["Locations"])


@router.get("/search")
async def search_locations(
    q: str = Query(min_length=1),
    destination: str | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    locations = await location_service.search_locations(db, q, destination, limit)
    return envelope(data=[LocationResponse.model_validate(loc) for loc in locations])


@router.get("/nearby")
async def search_nearby(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius: int = Query(default=1000, ge=50, le=50000),
    category: LocationCategory | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    results = await location_service.search_nearby(db, lat, lng, radius, category)
    return envelope(data=[NearbyLocationResponse(**r) for r in results])


@router.get("/{location_id}")
async def get_location_detail(
    location_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    location = await location_service.get_location_or_404(db, location_id)
    return envelope(data=LocationResponse.model_validate(location))


@router.post("")
async def upsert_location(
    payload: UpsertLocationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    location, created = await location_service.upsert_location_from_request(db, payload)
    response_data = UpsertLocationResponse.model_validate(location)

    if created:
        return envelope_created(data=response_data, message="Luu dia diem thanh cong")
    return envelope(data=response_data, message="Dia diem da co trong he thong")
