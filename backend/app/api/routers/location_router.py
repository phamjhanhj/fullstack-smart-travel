"""Router - Module 5: Locations (4 endpoints)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.rate_limit import rate_limit
from app.core.response import envelope, envelope_created
from app.db.session import get_db
from app.models.user import User
from app.schemas.location import (
    LocationCategory,
    LocationResponse,
    ExploreLocationsResponse,
    NearbyLocationResponse,
    SupportedDestinationResponse,
    UpsertLocationRequest,
    UpsertLocationResponse,
)
from app.services import location_service

router = APIRouter(prefix="/locations", tags=["Locations"])


@router.get(
    "/supported-destinations",
    dependencies=[Depends(rate_limit("location_supported", settings.RATE_LIMIT_SEARCH_PER_MINUTE))],
)
async def supported_destinations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items = await location_service.list_supported_destinations(db)
    return envelope(data=[SupportedDestinationResponse(**item) for item in items])


@router.get("/explore", dependencies=[Depends(rate_limit("location_explore", settings.RATE_LIMIT_SEARCH_PER_MINUTE))])
async def explore_locations(
    destination: str = Query(min_length=1, max_length=200),
    category: str | None = Query(default=None, max_length=50),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=36, ge=1, le=60),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await location_service.explore_dataset_locations(
        db,
        destination=destination,
        category=category,
        page=page,
        limit=limit,
    )
    return envelope(data=ExploreLocationsResponse(**result))


@router.get("/search", dependencies=[Depends(rate_limit("location_search", settings.RATE_LIMIT_SEARCH_PER_MINUTE))])
async def search_locations(
    q: str = Query(min_length=1, max_length=200),
    destination: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=50),
    include_external: bool = Query(default=True),
    limit: int = Query(default=30, ge=1, le=60),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    locations = await location_service.search_locations_hybrid(
        db,
        query=q,
        destination=destination,
        category=category,
        limit=limit,
        include_external=include_external,
    )
    return envelope(data=[LocationResponse.model_validate(loc) for loc in locations])


@router.get("/nearby", dependencies=[Depends(rate_limit("location_nearby", settings.RATE_LIMIT_SEARCH_PER_MINUTE))])
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
