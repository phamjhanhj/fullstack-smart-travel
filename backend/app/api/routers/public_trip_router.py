from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_optional_current_user, get_trip_owner_access
from app.core.response import envelope, envelope_created
from app.db.session import get_db
from app.models.trip import Trip
from app.models.user import User
from app.schemas.public_trip import (
    PublicationEligibilityResponse,
    PublicTripImportPreviewResponse,
    PublicTripImportRequest,
    PublicTripImportResponse,
    PublicTripListItem,
    PublicTripListResponse,
    PublicTripResponse,
    UpsertPublicTripRequest,
)
from app.services import public_trip_service, p2_service

trip_publication_router = APIRouter(
    prefix="/trips/{trip_id}/publication",
    tags=["Public Trips"],
)
public_trips_router = APIRouter(prefix="/public-trips", tags=["Public Trips"])


@trip_publication_router.get("/eligibility")
async def get_eligibility(
    trip: Trip = Depends(get_trip_owner_access),
    db: AsyncSession = Depends(get_db),
):
    data = await public_trip_service.publication_eligibility(db, trip)
    return envelope(data=PublicationEligibilityResponse(**data))


@trip_publication_router.get("")
async def get_owner_publication(
    trip: Trip = Depends(get_trip_owner_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    publication = await public_trip_service.get_owner_publication(db, trip.id, current_user.id)
    return envelope(
        data=PublicTripResponse(**public_trip_service.publication_payload(publication))
    )


@trip_publication_router.post("/draft", status_code=201)
async def save_publication_draft(
    payload: UpsertPublicTripRequest,
    trip: Trip = Depends(get_trip_owner_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    publication = await public_trip_service.upsert_publication(
        db, trip, current_user, payload, publish=False
    )
    return envelope_created(
        data=PublicTripResponse(**public_trip_service.publication_payload(publication)),
        message="Đã lưu bản nháp chia sẻ",
    )


@trip_publication_router.post("/publish")
async def publish_trip(
    payload: UpsertPublicTripRequest,
    trip: Trip = Depends(get_trip_owner_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    publication = await public_trip_service.upsert_publication(
        db, trip, current_user, payload, publish=True
    )
    await p2_service.notify_followers(db, publication)
    return envelope(
        data=PublicTripResponse(**public_trip_service.publication_payload(publication)),
        message="Đã xuất bản lịch trình chính thức",
    )


@trip_publication_router.post("/archive")
async def archive_trip_publication(
    trip: Trip = Depends(get_trip_owner_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    publication = await public_trip_service.get_owner_publication(db, trip.id, current_user.id)
    await public_trip_service.archive_publication(db, publication, current_user)
    return envelope(data=None, message="Đã ẩn lịch trình công khai")


@public_trips_router.get("")
async def list_public_trips(
    destination: str | None = Query(default=None, max_length=120),
    max_cost_per_person: int | None = Query(default=None, ge=0),
    min_days: int | None = Query(default=None, ge=1),
    max_days: int | None = Query(default=None, ge=1),
    sort: str = Query(default="newest"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    publications, total = await public_trip_service.list_publications(
        db,
        destination=destination,
        max_cost_per_person=max_cost_per_person,
        min_days=min_days,
        max_days=max_days,
        sort=sort,
        page=page,
        limit=limit,
    )
    saved_ids = await public_trip_service.saved_publication_ids(
        db, current_user.id, [publication.id for publication in publications]
    ) if current_user else set()
    items = [
        PublicTripListItem(**public_trip_service.publication_payload(
            publication, is_saved=publication.id in saved_ids
        ))
        for publication in publications
    ]
    return envelope(data=PublicTripListResponse(items=items, total=total, page=page, limit=limit))


@public_trips_router.get("/saved/me")
async def list_my_saved_public_trips(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=12, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    publications, total = await public_trip_service.list_saved_publications(
        db, current_user.id, page=page, limit=limit
    )
    items = [
        PublicTripListItem(**public_trip_service.publication_payload(publication, is_saved=True))
        for publication in publications
    ]
    return envelope(data=PublicTripListResponse(items=items, total=total, page=page, limit=limit))


@public_trips_router.post("/{publication_id}/save")
async def save_public_trip(
    publication_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    created = await public_trip_service.save_publication(db, publication_id, current_user.id)
    return envelope(data={"saved": True}, message="Đã lưu lịch trình" if created else "Lịch trình đã được lưu")


@public_trips_router.delete("/{publication_id}/save")
async def unsave_public_trip(
    publication_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await public_trip_service.unsave_publication(db, publication_id, current_user.id)
    return envelope(data={"saved": False}, message="Đã bỏ lưu lịch trình")


@public_trips_router.post("/{publication_id}/import-preview")
async def preview_public_trip_import(
    publication_id: uuid.UUID,
    payload: PublicTripImportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    publication = await public_trip_service.get_publication_by_id(db, publication_id)
    data = await public_trip_service.preview_import(db, publication, payload, current_user)
    return envelope(data=PublicTripImportPreviewResponse(**data))


@public_trips_router.post("/{publication_id}/import", status_code=201)
async def import_public_trip(
    publication_id: uuid.UUID,
    payload: PublicTripImportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    publication = await public_trip_service.get_publication_by_id(db, publication_id)
    data = await public_trip_service.import_publication(db, publication, payload, current_user)
    return envelope_created(
        data=PublicTripImportResponse(**data),
        message="Đã thêm lịch trình vào chuyến đi của bạn",
    )


@public_trips_router.get("/{slug}")
async def get_public_trip(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    publication = await public_trip_service.get_publication_by_slug(db, slug)
    saved_ids = await public_trip_service.saved_publication_ids(
        db, current_user.id, [publication.id]
    ) if current_user else set()
    return envelope(
        data=PublicTripResponse(**public_trip_service.publication_payload(
            publication, is_saved=publication.id in saved_ids, public_view=True
        ))
    )
