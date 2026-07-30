"""Publish completed trips as privacy-safe snapshots and reuse them deterministically."""
from __future__ import annotations

import re
import copy
import unicodedata
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.models.activity import Activity
from app.models.budget import BudgetItem
from app.models.location import Location
from app.models.public_trip import (
    ActivityPublicationSource,
    PublicTripImport,
    PublicTripPublication,
    PublicTripSave,
)
from app.models.trip import DayPlan, Trip
from app.models.user import User
from app.schemas.public_trip import PublicTripImportRequest, UpsertPublicTripRequest
from app.services import trip_history_service, trip_share_service


_SENSITIVE_PATTERNS = (
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+", re.I), "EMAIL_DETECTED"),
    (re.compile(r"(?<!\d)(?:\+?84|0)\d{8,10}(?!\d)"), "PHONE_DETECTED"),
    (re.compile(r"\b(?:booking|reservation|ma dat|mã đặt|pnr)\s*[:#-]?\s*[a-z0-9-]{5,}\b", re.I), "BOOKING_CODE_DETECTED"),
)


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn").replace("đ", "d")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _normalize(value)).strip("-")
    return slug[:180] or "lich-trinh"


def _privacy_issues(payload: UpsertPublicTripRequest) -> list[dict[str, str]]:
    texts = [
        payload.title,
        payload.summary,
        payload.would_change or "",
        payload.general_tips or "",
        *payload.best_places,
        *payload.best_foods,
        *(review.next_traveler_note or "" for review in payload.activity_reviews),
    ]
    issues: list[dict[str, str]] = []
    for text in texts:
        for pattern, code in _SENSITIVE_PATTERNS:
            if pattern.search(text):
                issues.append({"code": code, "message": "Nội dung có thể chứa thông tin riêng tư."})
    return issues


async def publication_summaries_by_trip_ids(
    db: AsyncSession, trip_ids: list[uuid.UUID]
) -> dict[uuid.UUID, PublicTripPublication]:
    if not trip_ids:
        return {}
    result = await db.execute(
        select(PublicTripPublication).where(
            PublicTripPublication.source_trip_id.in_(trip_ids),
            PublicTripPublication.status == "published",
        )
    )
    return {publication.source_trip_id: publication for publication in result.scalars().all()}

async def publication_eligibility(db: AsyncSession, trip: Trip) -> dict[str, Any]:
    blocking: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    days_result = await db.execute(
        select(DayPlan)
        .where(DayPlan.trip_id == trip.id)
        .options(selectinload(DayPlan.activities))
    )
    days = list(days_result.scalars().all())
    activities = [activity for day in days for activity in day.activities]
    experiences = [a for a in activities if a.type in {"attraction", "meal", "other"}]
    actual_cost_count = int(
        (
            await db.execute(
                select(func.count(BudgetItem.id)).where(
                    BudgetItem.trip_id == trip.id,
                    BudgetItem.actual_amount > 0,
                )
            )
        ).scalar_one()
    )
    if trip.status != "completed":
        blocking.append({"code": "TRIP_NOT_COMPLETED", "message": "Hãy đánh dấu chuyến đi đã hoàn thành."})
    if trip.end_date > date.today():
        blocking.append({"code": "TRIP_NOT_ENDED", "message": "Ngày kết thúc chuyến đi vẫn ở tương lai."})
    if not days:
        blocking.append({"code": "ITINERARY_EMPTY", "message": "Chuyến đi chưa có lịch trình."})
    if not experiences:
        blocking.append({"code": "EXPERIENCE_EMPTY", "message": "Chưa có hoạt động trải nghiệm để chia sẻ."})
    if actual_cost_count == 0:
        warnings.append({"code": "ACTUAL_COST_MISSING", "message": "Chưa có chi phí thực tế; bài sẽ ghi rõ là ước tính."})
    return {
        "eligible": not blocking,
        "blocking_reasons": blocking,
        "warnings": warnings,
        "completion": {
            "itinerary_percent": 100 if days and experiences else 0,
            "actual_cost_percent": 100 if actual_cost_count else 0,
            "review_percent": 0,
        },
    }


async def _load_trip_snapshot_source(db: AsyncSession, trip_id: uuid.UUID) -> tuple[list[DayPlan], list[BudgetItem]]:
    days_result = await db.execute(
        select(DayPlan)
        .where(DayPlan.trip_id == trip_id)
        .options(selectinload(DayPlan.activities).selectinload(Activity.location))
        .order_by(DayPlan.day_number)
    )
    budgets_result = await db.execute(
        select(BudgetItem).where(BudgetItem.trip_id == trip_id).order_by(BudgetItem.date, BudgetItem.created_at)
    )
    return list(days_result.scalars().all()), list(budgets_result.scalars().all())


async def build_snapshot(
    db: AsyncSession,
    trip: Trip,
    payload: UpsertPublicTripRequest,
) -> dict[str, Any]:
    days, budget_items = await _load_trip_snapshot_source(db, trip.id)
    reviews = {str(review.activity_id): review for review in payload.activity_reviews}
    snapshot_days: list[dict[str, Any]] = []
    activity_count = 0
    for day in days:
        public_activities: list[dict[str, Any]] = []
        for activity in day.activities:
            review = reviews.get(str(activity.id))
            actual_status = review.actual_status if review else "visited"
            if actual_status == "skipped":
                continue
            location = activity.location
            public_activities.append(
                {
                    "source_activity_id": str(activity.id),
                    "location_id": str(activity.location_id) if activity.location_id else None,
                    "title": activity.title,
                    "description": activity.description,
                    "type": activity.type,
                    "start_time": activity.start_time,
                    "end_time": activity.end_time,
                    "actual_status": actual_status,
                    "actual_cost": review.actual_cost if review and review.actual_cost is not None else activity.estimated_cost,
                    "author_verdict": review.author_verdict if review else "recommended",
                    "rating": review.rating if review else None,
                    "next_traveler_note": review.next_traveler_note if review else None,
                    "best_time": review.best_time if review else None,
                    "actual_wait_minutes": review.actual_wait_minutes if review else None,
                    "booking_required": review.booking_required if review else None,
                    "address": location.address if location else activity.description,
                    "lat": location.lat if location else None,
                    "lng": location.lng if location else None,
                    "coordinate_accuracy": location.coordinate_status if location else None,
                }
            )
            activity_count += 1
        snapshot_days.append(
            {
                "day_number": day.day_number,
                "title": f"Ngày {day.day_number}",
                "activities": public_activities,
                "actual_day_cost": sum(int(item.get("actual_cost") or 0) for item in public_activities),
            }
        )

    actual_budget = sum(int(item.actual_amount or 0) for item in budget_items)
    planned_budget = sum(int(item.planned_amount or 0) for item in budget_items)
    supplied_actual = payload.actual_total_cost
    actual_total = supplied_actual if supplied_actual is not None else (actual_budget or None)
    return {
        "schema_version": 1,
        "official_itinerary": True,
        "author_confirmed": payload.author_confirmed,
        "trip": {
            "destination": trip.destination,
            "duration_days": (trip.end_date - trip.start_date).days + 1,
            "traveler_type": payload.traveler_type,
            "travel_month": trip.start_date.month if payload.show_travel_month else None,
            "travel_year": trip.start_date.year if payload.show_travel_month else None,
            "original_travelers": trip.num_travelers,
        },
        "days": snapshot_days,
        "cost_summary": {
            "planned": planned_budget or trip.budget,
            "actual": actual_total if payload.show_cost else None,
            "per_person": (
                round(actual_total / max(trip.num_travelers, 1))
                if actual_total is not None and payload.show_cost
                else None
            ),
            "source": "actual" if actual_total is not None else "estimated",
        },
        "review": {
            "best_places": payload.best_places,
            "best_foods": payload.best_foods,
            "would_change": payload.would_change,
            "tips": payload.general_tips,
        },
        "activity_count": activity_count,
    }


async def _unique_slug(db: AsyncSession, title: str, existing_id: uuid.UUID | None = None) -> str:
    base = _slugify(title)
    slug = base
    suffix = 2
    while True:
        query = select(PublicTripPublication.id).where(PublicTripPublication.slug == slug)
        if existing_id:
            query = query.where(PublicTripPublication.id != existing_id)
        if (await db.execute(query)).scalar_one_or_none() is None:
            return slug
        slug = f"{base}-{suffix}"
        suffix += 1


async def get_owner_publication(db: AsyncSession, trip_id: uuid.UUID, user_id: uuid.UUID) -> PublicTripPublication:
    result = await db.execute(
        select(PublicTripPublication)
        .where(
            PublicTripPublication.source_trip_id == trip_id,
            PublicTripPublication.author_user_id == user_id,
            PublicTripPublication.status != "removed",
        )
        .options(selectinload(PublicTripPublication.author))
    )
    publication = result.scalar_one_or_none()
    if publication is None:
        raise NotFoundError("Chuyến đi chưa có bản chia sẻ công khai")
    return publication


async def upsert_publication(
    db: AsyncSession,
    trip: Trip,
    actor: User,
    payload: UpsertPublicTripRequest,
    *,
    publish: bool,
) -> PublicTripPublication:
    eligibility = await publication_eligibility(db, trip)
    if not eligibility["eligible"]:
        raise AppError(eligibility["blocking_reasons"][0]["message"], status_code=422)
    privacy_issues = _privacy_issues(payload)
    if privacy_issues:
        raise AppError(
            "Nội dung có thể chứa email, số điện thoại hoặc mã đặt chỗ. Hãy xóa trước khi công khai.",
            status_code=422,
        )
    if publish and not payload.author_confirmed:
        raise AppError("Bạn cần xác nhận đây là lịch trình thực tế chính thức.", status_code=422)

    existing_result = await db.execute(
        select(PublicTripPublication).where(
            PublicTripPublication.source_trip_id == trip.id,
            PublicTripPublication.status.in_(["draft", "published"]),
        )
    )
    publication = existing_result.scalar_one_or_none()
    snapshot = await build_snapshot(db, trip, payload)
    now = datetime.now(timezone.utc)
    ratings = [v for v in (payload.itinerary_rating, payload.cost_rating, payload.place_rating) if v]
    actual_total = snapshot["cost_summary"]["actual"]
    values = {
        "title": payload.title,
        "summary": payload.summary,
        "destination": trip.destination,
        "province_name": trip.destination,
        "cover_image_url": trip.cover_image_url,
        "visibility": payload.visibility,
        "status": "published" if publish else "draft",
        "moderation_status": "approved",
        "duration_days": (trip.end_date - trip.start_date).days + 1,
        "travel_month": trip.start_date.month if payload.show_travel_month else None,
        "travel_year": trip.start_date.year if payload.show_travel_month else None,
        "traveler_type": payload.traveler_type,
        "pace": payload.pace,
        "budget_style": payload.budget_style,
        "actual_total_cost": actual_total,
        "actual_cost_per_person": (
            round(actual_total / max(trip.num_travelers, 1)) if actual_total is not None else None
        ),
        "cost_is_verified": actual_total is not None,
        "itinerary_rating": payload.itinerary_rating,
        "cost_rating": payload.cost_rating,
        "place_rating": payload.place_rating,
        "overall_rating": round(sum(ratings) / len(ratings), 1) if ratings else None,
        "snapshot_json": snapshot,
        "privacy_options": {
            "show_travel_month": payload.show_travel_month,
            "show_author_name": payload.show_author_name,
            "show_cost": payload.show_cost,
        },
        "tags": list(dict.fromkeys(tag.strip() for tag in payload.tags if tag.strip())),
        "allow_clone": payload.allow_clone,
        "allow_partial_import": payload.allow_partial_import,
        "allow_comments": payload.allow_comments,
    }
    if publication is None:
        publication = PublicTripPublication(
            source_trip_id=trip.id,
            author_user_id=actor.id,
            slug=await _unique_slug(db, payload.title),
            snapshot_version=1,
            **values,
        )
        db.add(publication)
    else:
        for key, value in values.items():
            setattr(publication, key, value)
        publication.slug = await _unique_slug(db, payload.title, publication.id)
        publication.snapshot_version += 1

    if publish:
        publication.author_confirmed_at = now
        publication.published_at = publication.published_at or now
    await db.flush()
    await trip_history_service.record_history_event(
        db,
        trip_id=trip.id,
        actor_user_id=actor.id,
        entity_type="public_trip",
        entity_id=publication.id,
        action="published" if publish else "drafted",
        summary="Đã xuất bản lịch trình công khai" if publish else "Đã lưu bản nháp chia sẻ",
        metadata={"snapshot_version": publication.snapshot_version, "visibility": publication.visibility},
    )
    await db.commit()
    return await get_owner_publication(db, trip.id, actor.id)


async def archive_publication(db: AsyncSession, publication: PublicTripPublication, actor: User) -> None:
    publication.status = "archived"
    if publication.source_trip_id:
        await trip_history_service.record_history_event(
            db,
            trip_id=publication.source_trip_id,
            actor_user_id=actor.id,
            entity_type="public_trip",
            entity_id=publication.id,
            action="archived",
            summary="Đã ẩn lịch trình công khai",
        )
    await db.commit()


def _public_activity_key(publication_id: uuid.UUID, source_activity_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"aether-public:{publication_id}:{source_activity_id}"))


def publication_payload(
    publication: PublicTripPublication,
    *,
    is_saved: bool = False,
    public_view: bool = False,
) -> dict[str, Any]:
    show_name = (publication.privacy_options or {}).get("show_author_name", True)
    author = publication.author
    snapshot = copy.deepcopy(publication.snapshot_json)
    if public_view:
        for day in snapshot.get("days", []):
            for activity in day.get("activities", []):
                raw_key = str(activity.get("source_activity_id") or "")
                if raw_key:
                    activity["source_activity_id"] = _public_activity_key(publication.id, raw_key)
    return {
        **{column.name: getattr(publication, column.name) for column in PublicTripPublication.__table__.columns},
        "snapshot_json": snapshot,
        "overall_rating": float(publication.overall_rating) if publication.overall_rating is not None else None,
        "author": {
            "id": author.id,
            "full_name": author.full_name if show_name else "Người dùng Aether",
            "avatar_url": author.avatar_url if show_name else None,
        },
        "is_saved": is_saved,
    }


async def list_publications(
    db: AsyncSession,
    *,
    destination: str | None,
    max_cost_per_person: int | None,
    min_days: int | None,
    max_days: int | None,
    sort: str,
    page: int,
    limit: int,
) -> tuple[list[PublicTripPublication], int]:
    filters = [
        PublicTripPublication.status == "published",
        PublicTripPublication.visibility == "public",
        PublicTripPublication.moderation_status == "approved",
    ]
    if destination:
        filters.append(PublicTripPublication.destination.ilike(f"%{destination.strip()}%"))
    if max_cost_per_person is not None:
        filters.append(PublicTripPublication.actual_cost_per_person <= max_cost_per_person)
    if min_days is not None:
        filters.append(PublicTripPublication.duration_days >= min_days)
    if max_days is not None:
        filters.append(PublicTripPublication.duration_days <= max_days)
    order = {
        "most_saved": PublicTripPublication.save_count.desc(),
        "lowest_cost": PublicTripPublication.actual_cost_per_person.asc().nullslast(),
        "recommended": (
            PublicTripPublication.overall_rating.desc().nullslast(),
            PublicTripPublication.save_count.desc(),
        ),
    }.get(sort, PublicTripPublication.published_at.desc())
    count = int(
        (await db.execute(select(func.count(PublicTripPublication.id)).where(*filters))).scalar_one()
    )
    query = select(PublicTripPublication).where(*filters).options(selectinload(PublicTripPublication.author))
    query = query.order_by(*order) if isinstance(order, tuple) else query.order_by(order)
    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    return list(result.scalars().all()), count


async def get_publication_by_slug(
    db: AsyncSession,
    slug: str,
    *,
    include_unlisted: bool = True,
) -> PublicTripPublication:
    filters = [
        PublicTripPublication.slug == slug,
        PublicTripPublication.status == "published",
        PublicTripPublication.moderation_status == "approved",
    ]
    if not include_unlisted:
        filters.append(PublicTripPublication.visibility == "public")
    result = await db.execute(
        select(PublicTripPublication).where(*filters).options(selectinload(PublicTripPublication.author))
    )
    publication = result.scalar_one_or_none()
    if publication is None:
        raise NotFoundError("Không tìm thấy lịch trình công khai")
    await db.execute(
        update(PublicTripPublication)
        .where(PublicTripPublication.id == publication.id)
        .values(view_count=PublicTripPublication.view_count + 1)
    )
    await db.commit()
    await db.refresh(publication)
    return publication


async def saved_publication_ids(
    db: AsyncSession, user_id: uuid.UUID, publication_ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    if not publication_ids:
        return set()
    result = await db.execute(
        select(PublicTripSave.publication_id).where(
            PublicTripSave.user_id == user_id,
            PublicTripSave.publication_id.in_(publication_ids),
        )
    )
    return set(result.scalars().all())

async def save_publication(db: AsyncSession, publication_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    publication = (
        await db.execute(
            select(PublicTripPublication).where(
                PublicTripPublication.id == publication_id,
                PublicTripPublication.status == "published",
            )
        )
    ).scalar_one_or_none()
    if publication is None:
        raise NotFoundError("Không tìm thấy lịch trình công khai")
    existing = (
        await db.execute(
            select(PublicTripSave).where(
                PublicTripSave.publication_id == publication_id,
                PublicTripSave.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return False
    db.add(PublicTripSave(publication_id=publication_id, user_id=user_id))
    publication.save_count += 1
    await db.commit()
    return True


async def unsave_publication(db: AsyncSession, publication_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    existing = (
        await db.execute(
            select(PublicTripSave).where(
                PublicTripSave.publication_id == publication_id,
                PublicTripSave.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        return False
    publication = await db.get(PublicTripPublication, publication_id)
    await db.delete(existing)
    if publication:
        publication.save_count = max(publication.save_count - 1, 0)
    await db.commit()
    return True


async def list_saved_publications(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    page: int,
    limit: int,
) -> tuple[list[PublicTripPublication], int]:
    filters = [
        PublicTripSave.user_id == user_id,
        PublicTripPublication.status == "published",
    ]
    count = int(
        (
            await db.execute(
                select(func.count(PublicTripSave.id))
                .join(PublicTripPublication, PublicTripPublication.id == PublicTripSave.publication_id)
                .where(*filters)
            )
        ).scalar_one()
    )
    result = await db.execute(
        select(PublicTripPublication)
        .join(PublicTripSave, PublicTripSave.publication_id == PublicTripPublication.id)
        .where(*filters)
        .options(selectinload(PublicTripPublication.author))
        .order_by(PublicTripSave.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return list(result.scalars().all()), count


async def get_publication_by_id(db: AsyncSession, publication_id: uuid.UUID) -> PublicTripPublication:
    result = await db.execute(
        select(PublicTripPublication).where(
            PublicTripPublication.id == publication_id,
            PublicTripPublication.status == "published",
        )
    )
    publication = result.scalar_one_or_none()
    if publication is None:
        raise NotFoundError("Không tìm thấy lịch trình công khai")
    return publication


def _selected_snapshot_activities(publication: PublicTripPublication, payload: PublicTripImportRequest) -> list[tuple[int, dict]]:
    selected: list[tuple[int, dict]] = []
    selected_ids = set(payload.source_activity_ids)
    for day in publication.snapshot_json.get("days", []):
        day_number = int(day.get("day_number") or 0)
        if payload.import_mode == "day" and day_number != payload.source_day_number:
            continue
        for activity in day.get("activities", []):
            if payload.import_mode == "activity":
                raw_key = str(activity.get("source_activity_id") or "")
                public_key = _public_activity_key(publication.id, raw_key)
                if raw_key not in selected_ids and public_key not in selected_ids:
                    continue
            selected.append((day_number, activity))
    return selected


async def preview_import(
    db: AsyncSession,
    publication: PublicTripPublication,
    payload: PublicTripImportRequest,
    user: User,
) -> dict[str, Any]:
    if payload.import_mode == "full_trip" and not publication.allow_clone:
        raise ForbiddenError("Tác giả không cho phép sao chép toàn bộ lịch trình")
    if payload.import_mode != "full_trip" and not publication.allow_partial_import:
        raise ForbiddenError("Tác giả không cho phép thêm từng phần lịch trình")
    if payload.target_trip_id and not await trip_share_service.user_can_edit_trip(db, payload.target_trip_id, user.id):
        raise ForbiddenError("Bạn không có quyền chỉnh sửa chuyến đi đích")
    selected = _selected_snapshot_activities(publication, payload)
    if not selected:
        raise AppError("Không có hoạt động phù hợp để thêm", status_code=422)
    conflicts: list[dict[str, Any]] = []
    if payload.target_day_plan_id:
        day = (
            await db.execute(
                select(DayPlan)
                .where(DayPlan.id == payload.target_day_plan_id)
                .options(selectinload(DayPlan.activities))
            )
        ).scalar_one_or_none()
        if day is None or not await trip_share_service.user_can_edit_trip(db, day.trip_id, user.id):
            raise ForbiddenError("Bạn không có quyền chỉnh sửa ngày đích")
        existing_location_ids = {str(a.location_id) for a in day.activities if a.location_id}
        for _day_number, item in selected:
            if item.get("location_id") in existing_location_ids:
                conflicts.append({"code": "DUPLICATE_LOCATION", "message": f"{item['title']} đã có trong ngày đích."})
            for current in day.activities:
                if (
                    item.get("start_time")
                    and item.get("end_time")
                    and current.start_time
                    and current.end_time
                    and item["start_time"] < current.end_time
                    and item["end_time"] > current.start_time
                ):
                    conflicts.append({"code": "TIME_OVERLAP", "message": f"{item['title']} trùng giờ với {current.title}."})
                    break
    return {
        "can_import": not any(item["code"] == "DUPLICATE_LOCATION" for item in conflicts),
        "items": [
            {
                "source_day_number": day_number,
                "source_activity_id": item.get("source_activity_id"),
                "title": item.get("title"),
                "status": "ready",
                "suggested_start_time": item.get("start_time"),
            }
            for day_number, item in selected
        ],
        "conflicts": conflicts,
        "estimated_added_cost": sum(int(item.get("actual_cost") or 0) for _, item in selected),
        "requires_route_reoptimization": bool(conflicts) or len(selected) > 1,
    }


async def import_publication(
    db: AsyncSession,
    publication: PublicTripPublication,
    payload: PublicTripImportRequest,
    user: User,
) -> dict[str, Any]:
    preview = await preview_import(db, publication, payload, user)
    if not preview["can_import"]:
        raise AppError("Có địa điểm trùng trong ngày đích. Hãy chọn ngày khác.", status_code=409)
    selected = _selected_snapshot_activities(publication, payload)
    warnings = [item["message"] for item in preview["conflicts"]]
    days_by_number: dict[int, DayPlan] = {}
    if payload.import_mode == "full_trip":
        assert payload.start_date is not None
        duration = publication.duration_days
        trip = Trip(
            user_id=user.id,
            title=payload.title or f"{publication.title} - bản của tôi",
            destination=publication.destination,
            start_date=payload.start_date,
            end_date=payload.start_date + timedelta(days=duration - 1),
            budget=payload.budget,
            num_travelers=payload.num_travelers,
            preferences=f"Tham khảo từ lịch trình công khai: {publication.title}",
            status="draft",
            cover_image_url=publication.cover_image_url,
        )
        db.add(trip)
        await db.flush()
        for number in range(1, duration + 1):
            day = DayPlan(trip_id=trip.id, day_number=number, date=payload.start_date + timedelta(days=number - 1))
            db.add(day)
            await db.flush()
            days_by_number[number] = day
    else:
        target_day = await db.get(DayPlan, payload.target_day_plan_id)
        if target_day is None:
            raise NotFoundError("Không tìm thấy ngày đích")
        trip = await db.get(Trip, target_day.trip_id)
        if trip is None:
            raise NotFoundError("Không tìm thấy chuyến đi đích")
        for source_day, _item in selected:
            days_by_number[source_day] = target_day

    imported = 0
    for source_day, item in selected:
        target_day = days_by_number.get(source_day)
        if target_day is None:
            continue
        location_id = None
        if item.get("location_id"):
            try:
                candidate_id = uuid.UUID(item["location_id"])
                location = await db.get(Location, candidate_id)
                if location and getattr(location, "status", "active") == "active":
                    location_id = location.id
                else:
                    warnings.append(f"{item['title']}: địa điểm hiện không còn active trong Data.")
            except ValueError:
                pass
        activity = Activity(
            day_plan_id=target_day.id,
            location_id=location_id,
            title=str(item.get("title") or "Hoạt động tham khảo"),
            description=item.get("description") or item.get("address"),
            type=item.get("type") or "other",
            start_time=item.get("start_time"),
            end_time=item.get("end_time"),
            estimated_cost=int(item.get("actual_cost") or 0),
            order_index=imported,
            notes=(
                f"[Tham khảo từ {publication.title}] "
                f"{item.get('next_traveler_note') or ''}"
            ).strip(),
        )
        db.add(activity)
        await db.flush()
        db.add(
            ActivityPublicationSource(
                activity_id=activity.id,
                publication_id=publication.id,
                snapshot_version=publication.snapshot_version,
                source_day_number=source_day,
                source_activity_key=str(item.get("source_activity_id") or activity.id),
                imported_by_user_id=user.id,
                author_verdict=item.get("author_verdict"),
                author_note_snapshot=item.get("next_traveler_note"),
            )
        )
        imported += 1

    db.add(
        PublicTripImport(
            publication_id=publication.id,
            target_trip_id=trip.id,
            user_id=user.id,
            import_mode=payload.import_mode,
            source_day_number=payload.source_day_number,
            source_activity_key=(payload.source_activity_ids[0] if len(payload.source_activity_ids) == 1 else None),
            target_day_plan_id=payload.target_day_plan_id,
        )
    )
    publication.clone_count += 1
    await db.commit()
    return {
        "trip_id": trip.id,
        "day_plan_id": payload.target_day_plan_id,
        "imported_activities": imported,
        "warnings": warnings,
    }
