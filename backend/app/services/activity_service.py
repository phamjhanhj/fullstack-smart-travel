"""Business logic - Module 4: Day Plans & Activities."""
from __future__ import annotations

import json
import uuid
from datetime import timedelta
import math
import re
import time
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.models.activity import Activity
from app.models.trip import DayPlan, Trip
from app.models.location import Location
from app.models.user import User
from app.services import trip_share_service
from app.services import trip_history_service
from app.schemas.day_plan import (
    CreateActivityRequest,
    GenerateDaysRequest,
    ItineraryGenerationSummary,
    ItineraryIssue,
    ItineraryQualityResponse,
    ReorderActivitiesRequest,
    UpdateActivityRequest,
    UserRequestCoverage,
    UserRequestCoverageItem,
)
from app.services.destination_profile_service import build_destination_profile
from app.services.trip_intent_service import (
    extract_place_requests_from_preferences,
    resolve_trip_intent,
)


async def list_days_with_activities(db: AsyncSession, trip_id: uuid.UUID) -> list[DayPlan]:
    """GET /trips/{id}/days - toan bo ngay kem activities long nhau, sap theo day_number."""
    result = await db.execute(
        select(DayPlan)
        .where(DayPlan.trip_id == trip_id)
        .options(selectinload(DayPlan.activities).selectinload(Activity.location))
        .order_by(DayPlan.day_number)
    )
    return list(result.scalars().all())


async def check_itinerary_quality(db: AsyncSession, trip_id: uuid.UUID) -> ItineraryQualityResponse:
    """Run deterministic checks that can be shown while a trip is edited."""
    days = await list_days_with_activities(db, trip_id)
    issues: list[ItineraryIssue] = []
    for day in days:
        activities = sorted(day.activities, key=lambda item: (item.start_time or "99:99", item.order_index))
        if not activities:
            issues.append(ItineraryIssue(code="EMPTY_DAY", severity="warning", message=f"Ngày {day.day_number} chưa có hoạt động.", day_id=day.id))
            continue

        timed = [item for item in activities if item.start_time and item.end_time]
        for index, current in enumerate(timed):
            for following in timed[index + 1:]:
                if following.start_time >= current.end_time:
                    break
                issues.append(ItineraryIssue(
                    code="TIME_OVERLAP",
                    severity="error",
                    message=f'"{current.title}" bị trùng giờ với "{following.title}".',
                    day_id=day.id,
                    activity_ids=[current.id, following.id],
                ))

        if not any(item.type == "meal" for item in activities):
            issues.append(ItineraryIssue(code="MISSING_MEAL", severity="warning", message=f"Ngày {day.day_number} chưa có điểm ăn uống.", day_id=day.id))

        scheduled_minutes = 0
        for item in timed:
            start_hour, start_minute = (int(part) for part in item.start_time.split(":"))
            end_hour, end_minute = (int(part) for part in item.end_time.split(":"))
            scheduled_minutes += max(0, end_hour * 60 + end_minute - start_hour * 60 - start_minute)
        if scheduled_minutes > 720:
            issues.append(ItineraryIssue(code="OVERLOADED_DAY", severity="warning", message=f"Ngày {day.day_number} có hơn 12 giờ hoạt động, nên thêm thời gian nghỉ.", day_id=day.id))

    error_count = sum(issue.severity == "error" for issue in issues)
    warning_count = sum(issue.severity == "warning" for issue in issues)
    return ItineraryQualityResponse(
        score=max(0, 100 - error_count * 20 - warning_count * 5),
        error_count=error_count,
        warning_count=warning_count,
        issues=issues,
    )


async def get_day_or_404(db: AsyncSession, trip_id: uuid.UUID, day_id: uuid.UUID) -> DayPlan:
    """GET /trips/{id}/days/{day_id} - kiem tra day thuoc dung trip."""
    result = await db.execute(
        select(DayPlan)
        .where(DayPlan.id == day_id, DayPlan.trip_id == trip_id)
        # DayPlanResponse serializes each activity's nested location. Eager-load
        # it here so async response validation never attempts a lazy DB query.
        .options(selectinload(DayPlan.activities).selectinload(Activity.location))
    )
    day_plan = result.scalar_one_or_none()
    if day_plan is None:
        raise NotFoundError("Khong tim thay ngay nay trong chuyen di")
    return day_plan


async def create_activity(
    db: AsyncSession,
    trip_id: uuid.UUID,
    day_id: uuid.UUID,
    payload: CreateActivityRequest,
    actor: User,
) -> Activity:
    """POST /trips/{id}/days/{day_id}/activities."""
    await get_day_or_404(db, trip_id, day_id)  # dam bao day thuoc dung trip

    activity = Activity(day_plan_id=day_id, **payload.model_dump())
    db.add(activity)
    await db.flush()
    await trip_history_service.record_history_event(
        db,
        trip_id=trip_id,
        actor_user_id=actor.id,
        entity_type="activity",
        entity_id=activity.id,
        action="created",
        summary=f"Da them hoat dong \"{activity.title}\"",
        metadata={"day_id": day_id, "title": activity.title},
    )
    await db.commit()
    return await _get_activity_for_response(db, activity.id)


async def _get_activity_for_response(db: AsyncSession, activity_id: uuid.UUID) -> Activity:
    result = await db.execute(
        select(Activity)
        .where(Activity.id == activity_id)
        .options(selectinload(Activity.location))
    )
    activity = result.scalar_one_or_none()
    if activity is None:
        raise NotFoundError("Khong tim thay hoat dong nay")
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


async def get_activity_editable_or_404(db: AsyncSession, activity_id: uuid.UUID, user_id: uuid.UUID) -> Activity:
    """Lay activity neu user la owner hoac editor cua trip chua activity."""
    result = await db.execute(
        select(Activity)
        .join(DayPlan, Activity.day_plan_id == DayPlan.id)
        .where(Activity.id == activity_id)
        .options(selectinload(Activity.day_plan))
    )
    activity = result.scalar_one_or_none()
    if activity is None:
        raise NotFoundError("Khong tim thay hoat dong nay")
    day_plan = activity.day_plan
    if not await trip_share_service.user_can_edit_trip(db, day_plan.trip_id, user_id):
        raise ForbiddenError("Ban khong co quyen chinh sua hoat dong nay")
    return activity


async def update_activity(
    db: AsyncSession,
    activity: Activity,
    payload: UpdateActivityRequest,
    actor: User,
) -> Activity:
    tracked_fields = list(trip_history_service.ACTIVITY_FIELD_LABELS.keys())
    before = trip_history_service.snapshot_fields(activity, tracked_fields)
    update_data = payload.model_dump(exclude_unset=True)
    final_start_time = update_data.get("start_time", activity.start_time)
    final_end_time = update_data.get("end_time", activity.end_time)
    if final_start_time and final_end_time and final_end_time <= final_start_time:
        raise AppError("Giờ kết thúc phải sau giờ bắt đầu.", status_code=422)
    for field, value in update_data.items():
        setattr(activity, field, value)

    await db.flush()
    after = trip_history_service.snapshot_fields(activity, tracked_fields)
    changes = trip_history_service.diff_snapshots(
        before,
        after,
        trip_history_service.ACTIVITY_FIELD_LABELS,
    )
    if changes:
        await trip_history_service.record_history_event(
            db,
            trip_id=activity.day_plan.trip_id,
            actor_user_id=actor.id,
            entity_type="activity",
            entity_id=activity.id,
            action="updated",
            summary=f"Da cap nhat hoat dong \"{activity.title}\"",
            changes=changes,
            metadata={"day_id": activity.day_plan_id},
        )
    await db.commit()
    return await _get_activity_for_response(db, activity.id)


async def delete_activity(db: AsyncSession, activity: Activity, actor: User) -> None:
    await trip_history_service.record_history_event(
        db,
        trip_id=activity.day_plan.trip_id,
        actor_user_id=actor.id,
        entity_type="activity",
        entity_id=activity.id,
        action="deleted",
        summary=f"Da xoa hoat dong \"{activity.title}\"",
        metadata={"day_id": activity.day_plan_id, "title": activity.title},
    )
    await db.delete(activity)
    await db.commit()


async def reorder_activities(db: AsyncSession, actor: User, payload: ReorderActivitiesRequest) -> None:
    """
    PATCH /activities/reorder - cap nhat order_index hang loat.
    Kiem tra day_plan_id thuoc trip cua user truoc khi update bat ky activity nao.
    """
    day_result = await db.execute(select(DayPlan).where(DayPlan.id == payload.day_plan_id))
    day_plan = day_result.scalar_one_or_none()
    if day_plan is None or not await trip_share_service.user_can_edit_trip(db, day_plan.trip_id, actor.id):
        raise ForbiddenError("Ban khong co quyen sap xep ngay nay")

    activity_ids = [item.id for item in payload.items]
    result = await db.execute(
        select(Activity).where(Activity.id.in_(activity_ids), Activity.day_plan_id == payload.day_plan_id)
    )
    activities_by_id = {a.id: a for a in result.scalars().all()}

    if len(activities_by_id) != len(activity_ids):
        raise AppError("Mot so hoat dong khong thuoc ngay nay", status_code=400)

    changes: list[dict] = []
    for item in payload.items:
        activity = activities_by_id[item.id]
        before_order = activity.order_index
        activity.order_index = item.order_index
        if before_order != item.order_index:
            changes.append(
                {
                    "field": "order_index",
                    "label": "Thu tu",
                    "before": before_order,
                    "after": item.order_index,
                    "activity_id": str(activity.id),
                    "activity_title": activity.title,
                }
            )

    if changes:
        await trip_history_service.record_history_event(
            db,
            trip_id=day_plan.trip_id,
            actor_user_id=actor.id,
            entity_type="activity",
            entity_id=payload.day_plan_id,
            action="reordered",
            summary=f"Da sap xep lai hoat dong ngay {day_plan.day_number}",
            changes=changes,
            metadata={"day_id": payload.day_plan_id, "day_number": day_plan.day_number},
        )
    await db.commit()


async def _generate_day_plans_legacy(db: AsyncSession, trip: Trip, overwrite: bool) -> list[DayPlan]:
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


async def generate_day_plans(
    db: AsyncSession,
    trip: Trip,
    payload: GenerateDaysRequest | bool,
    actor: User,
) -> tuple[list[DayPlan], ItineraryGenerationSummary]:
    """
    Generate a grounded itinerary:
    location discovery -> AI generation -> validation/repair -> deterministic fallback -> DB save.
    """
    if isinstance(payload, bool):
        payload = GenerateDaysRequest(overwrite=payload)

    generation_id = str(uuid.uuid4())
    generation_started = time.perf_counter()
    timings_ms: dict[str, int] = {}
    fallback_reason: str | None = None

    total_days = (trip.end_date - trip.start_date).days + 1
    if total_days <= 0:
        raise AppError("Ngay ket thuc phai lon hon hoac bang ngay bat dau", status_code=400)

    existing_count = await db.execute(select(DayPlan).where(DayPlan.trip_id == trip.id))
    if not payload.overwrite and existing_count.scalars().first() is not None:
        raise AppError("Chuyen di da co lich trinh, dung overwrite=true de tao lai", status_code=400)

    if not payload.ai:
        if payload.overwrite:
            existing = await db.execute(select(DayPlan).where(DayPlan.trip_id == trip.id))
            for day in existing.scalars().all():
                await db.delete(day)
            await db.flush()

        new_days = [
            DayPlan(trip_id=trip.id, day_number=i, date=trip.start_date + timedelta(days=i - 1))
            for i in range(1, total_days + 1)
        ]
        db.add_all(new_days)
        await db.flush()

        summary = ItineraryGenerationSummary(
            total_estimated_cost=0,
            budget_limit=trip.budget,
            budget_used_percent=0,
            included_user_places=[],
            missing_user_places=[],
            candidate_places_count=0,
            warnings=[]
        )
        await trip_history_service.record_history_event(
            db,
            trip_id=trip.id,
            actor_user_id=actor.id,
            entity_type="itinerary",
            entity_id=trip.id,
            action="generated",
            summary=f"Da tao {len(new_days)} ngay lich trinh",
            metadata={
                "days_created": len(new_days),
                "overwrite": payload.overwrite,
                "ai": False,
                "generation_summary": summary.model_dump(),
            },
        )
        await db.commit()
        for day in new_days:
            await db.refresh(day)

        return new_days, summary

    candidate_started = time.perf_counter()
    user_interests = await _load_user_interests(db, trip.user_id)
    weighted_interests = [
        interest
        for interest, _weight in sorted(
            payload.interest_weights.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        if _weight > 0
    ]
    user_interests = _merge_unique([*weighted_interests, *user_interests])
    resolved_intent = resolve_trip_intent(payload)
    payload.accept_long_daily_travel = resolved_intent.accept_long_daily_travel
    payload.early_start_allowed = resolved_intent.early_start_allowed
    payload.night_driving_allowed = resolved_intent.night_driving_allowed
    # Explicit generation requirements stay strict. Place-like clauses from the
    # dashboard are resolved against Data below; resolved places are then locked.
    strict_must_visit = _merge_unique(resolved_intent.required_names)[:20]
    preference_place_requests = extract_place_requests_from_preferences(trip.preferences)
    discovery_requests = _merge_unique(
        [*strict_must_visit, *preference_place_requests]
    )[:20]
    avoid_places = _merge_unique(payload.avoid_places)[:12]

    from app.services.location_service import discover_itinerary_candidates

    candidates = await discover_itinerary_candidates(
        db,
        destination=trip.destination,
        must_visit=discovery_requests,
        must_visit_location_ids=resolved_intent.required_location_ids,
        interests=user_interests,
        allow_external_fallback=settings.ITINERARY_ONLINE_FALLBACK,
    )
    candidates = _filter_avoided_candidates(candidates, avoid_places)
    preference_request_keys = {
        _normalize_text(place) for place in preference_place_requests
    }
    resolved_preference_places = _merge_unique(
        str(item["must_visit_match"])
        for item in candidates
        if item.get("must_visit_match")
        and _normalize_text(str(item["must_visit_match"])) in preference_request_keys
    )
    must_visit = _merge_unique(
        [*strict_must_visit, *resolved_preference_places]
    )[:20]
    allowed_must_visit = {_normalize_text(place) for place in must_visit}
    for item in candidates:
        match = item.get("must_visit_match")
        if match and _normalize_text(str(match)) not in allowed_must_visit:
            item["must_visit_match"] = None

    required_candidates = [
        item for item in candidates if item.get("must_visit_match")
    ]
    if _has_long_required_leg(required_candidates, minimum_meters=40_000):
        payload.accept_long_daily_travel = True
        payload.max_daily_travel_minutes = max(payload.max_daily_travel_minutes, 360)

    candidates_by_ref = {item["ref"]: item for item in candidates if item.get("ref")}
    required_location_refs = {
        item["ref"]
        for item in candidates
        if item.get("ref") and item.get("must_visit_match")
    }
    destination_profile = build_destination_profile(trip.destination, candidates)
    timings_ms["candidate_ms"] = round((time.perf_counter() - candidate_started) * 1000)

    itinerary_data: dict | None = None
    validation_errors: list[str] = []
    experience_warnings: list[str] = []
    fact_warnings: list[str] = []
    planning_mode = "grounded_v2"

    if candidates:
        from app.services.ai_service import generate_grounded_itinerary_with_ai
        from app.services.itinerary_verifier import verify_grounded_itinerary

        max_ai_calls = min(max(settings.ITINERARY_MAX_AI_CALLS, 0), 1)
        for _attempt in range(max_ai_calls):
            try:
                ai_started = time.perf_counter()
                generated_data = await generate_grounded_itinerary_with_ai(
                    trip,
                    candidates,
                    pace=payload.pace,
                    must_visit=must_visit,
                    interests=user_interests,
                    avoid_places=avoid_places,
                    budget_mode=payload.budget_mode,
                    prioritize_user_places=payload.prioritize_user_places,
                    transport_mode=payload.transport_mode,
                    departure_location=payload.departure_location,
                    departure_time=payload.departure_time,
                    estimated_travel_hours=payload.estimated_travel_hours,
                    arrival_transport=payload.arrival_transport,
                    daily_start_time=payload.daily_start_time,
                    daily_end_time=payload.daily_end_time,
                    dietary_notes=payload.dietary_notes,
                    mobility_notes=payload.mobility_notes,
                    user_notes=payload.user_notes,
                    destination_profile=destination_profile,
                    accept_long_daily_travel=payload.accept_long_daily_travel,
                    max_daily_travel_minutes=payload.max_daily_travel_minutes,
                    validation_errors=[],
                    draft_itinerary=None,
                )
                timings_ms["groq_first_ms"] = round((time.perf_counter() - ai_started) * 1000)
                verify_started = time.perf_counter()
                itinerary_data = _sanitize_itinerary(generated_data, total_days, candidates_by_ref)
                _enforce_closed_loop_itinerary(itinerary_data, trip, candidates, total_days, payload)
                experience_warnings = _enrich_experience_route(itinerary_data, trip, candidates, total_days, payload)
                experience_warnings.extend(
                    _lock_required_visits(itinerary_data, trip, candidates, total_days, payload)
                )
                experience_warnings.extend(
                    _diversify_meals(itinerary_data, candidates_by_ref, max_family_repeats=2)
                )
                validation_errors = _validate_itinerary(
                    itinerary_data,
                    total_days=total_days,
                    candidates_by_ref=candidates_by_ref,
                    budget=trip.budget,
                    budget_mode=payload.budget_mode,
                    payload=payload,
                )
                fact_issues = await verify_grounded_itinerary(
                    itinerary_data,
                    candidates_by_ref=candidates_by_ref,
                    start_date=trip.start_date,
                    transport_mode=payload.transport_mode,
                    required_location_refs=required_location_refs,
                )
                validation_errors = _merge_unique(
                    [
                        *validation_errors,
                        *(issue.as_prompt_text() for issue in fact_issues if issue.severity == "error"),
                    ]
                )
                fact_warnings = _merge_unique(
                    issue.as_prompt_text() for issue in fact_issues if issue.severity == "warning"
                )
                timings_ms["local_verify_ms"] = round((time.perf_counter() - verify_started) * 1000)
                if not validation_errors:
                    break
                fallback_reason = "validation_failed"
            except AppError as exc:
                timings_ms["groq_first_ms"] = round((time.perf_counter() - ai_started) * 1000)
                validation_errors = [str(exc)]
                itinerary_data = None
                fallback_reason = "groq_timeout" if exc.status_code == 504 else "groq_error"
                break

    if itinerary_data is None or validation_errors:
        planning_mode = "fallback"
        fallback_reason = fallback_reason or ("no_candidates" if not candidates else "validation_failed")
        fallback_started = time.perf_counter()
        itinerary_data = _build_fallback_itinerary(
            trip,
            candidates,
            total_days=total_days,
            pace=payload.pace,
        )
        _enforce_closed_loop_itinerary(itinerary_data, trip, candidates, total_days, payload)
        experience_warnings = _enrich_experience_route(itinerary_data, trip, candidates, total_days, payload)
        experience_warnings.extend(
            _lock_required_visits(itinerary_data, trip, candidates, total_days, payload)
        )
        experience_warnings.extend(
            _diversify_meals(itinerary_data, candidates_by_ref, max_family_repeats=2)
        )
        validation_errors = _validate_itinerary(
            itinerary_data,
            total_days=total_days,
            candidates_by_ref=candidates_by_ref,
            budget=trip.budget,
            budget_mode=payload.budget_mode,
            payload=payload,
        )
        if validation_errors:
            _fit_itinerary_to_budget(itinerary_data, trip.budget, payload.budget_mode)
        if candidates:
            from app.services.itinerary_verifier import verify_grounded_itinerary

            fallback_issues = await verify_grounded_itinerary(
                itinerary_data,
                candidates_by_ref=candidates_by_ref,
                start_date=trip.start_date,
                transport_mode=payload.transport_mode,
                required_location_refs=required_location_refs,
            )
            fact_warnings = _merge_unique(
                [
                    *fact_warnings,
                    *(issue.as_prompt_text() for issue in fallback_issues),
                ]
            )
        timings_ms["fallback_ms"] = round((time.perf_counter() - fallback_started) * 1000)

    _apply_grounded_candidate_costs(
        itinerary_data,
        trip,
        candidates_by_ref,
        payload.budget_mode,
    )
    _apply_realistic_costs(itinerary_data, trip, payload.budget_mode)
    budget_trim_warning = _trim_optional_experiences_to_budget(
        itinerary_data,
        trip.budget,
        payload.budget_mode,
        candidates_by_ref,
        payload,
    )
    if budget_trim_warning:
        experience_warnings.append(budget_trim_warning)
    _fit_itinerary_to_budget(itinerary_data, trip.budget, payload.budget_mode)

    summary = _build_generation_summary(
        itinerary_data,
        candidates_by_ref=candidates_by_ref,
        must_visit=must_visit,
        budget=trip.budget,
        budget_mode=payload.budget_mode,
        candidate_places_count=len(candidates),
        warnings=_merge_unique([*validation_errors, *experience_warnings, *fact_warnings]),
        planning_mode=planning_mode,
        destination_topology=destination_profile["topology"],
        generation_id=generation_id,
        generation_timings_ms=timings_ms,
        fallback_reason=fallback_reason,
    )

    if summary.missing_user_places:
        missing_text = ", ".join(summary.missing_user_places)
        raise AppError(
            (
                "Không thể tạo lịch trình mà vẫn bảo đảm các điểm bắt buộc: "
                f"{missing_text}. Hãy tăng số ngày, đổi giờ xuất phát hoặc kiểm tra lại tên địa điểm."
            ),
            status_code=422,
        )

    persist_started = time.perf_counter()
    if payload.overwrite:
        existing = await db.execute(select(DayPlan).where(DayPlan.trip_id == trip.id))
        for day in existing.scalars().all():
            await db.delete(day)
        await db.flush()

    new_days = [
        DayPlan(trip_id=trip.id, day_number=i, date=trip.start_date + timedelta(days=i - 1))
        for i in range(1, total_days + 1)
    ]
    db.add_all(new_days)
    await db.flush()

    day_map = {day.day_number: day for day in new_days}

    for day_data in itinerary_data.get("days", []):
        day_plan = day_map.get(day_data.get("day_number"))
        if not day_plan:
            continue
        for idx, act_data in enumerate(day_data.get("activities", [])):
            db.add(
                Activity(
                    day_plan_id=day_plan.id,
                    location_id=_resolve_location_id(act_data, candidates_by_ref),
                    title=(act_data.get("title") or "Hoat dong")[:200],
                    description=act_data.get("description"),
                    type=_sanitize_type(act_data.get("type")),
                    start_time=_sanitize_time(act_data.get("start_time")),
                    end_time=_sanitize_time(act_data.get("end_time")),
                    estimated_cost=_sanitize_cost(act_data.get("estimated_cost")),
                    notes=_merge_activity_notes(act_data),
                    order_index=idx,
                )
            )

    await db.flush()
    total_activities = sum(
        len(day_data.get("activities", []))
        for day_data in itinerary_data.get("days", [])
        if isinstance(day_data, dict)
    )
    await trip_history_service.record_history_event(
        db,
        trip_id=trip.id,
        actor_user_id=actor.id,
        entity_type="itinerary",
        entity_id=trip.id,
        action="generated",
        summary=f"Da tao lich trinh AI gom {len(new_days)} ngay",
        metadata={
            "days_created": len(new_days),
            "activities_created": total_activities,
            "overwrite": payload.overwrite,
            "ai": True,
            "generation_summary": summary.model_dump(),
        },
    )
    await db.commit()
    timings_ms["persist_ms"] = round((time.perf_counter() - persist_started) * 1000)
    timings_ms["total_ms"] = round((time.perf_counter() - generation_started) * 1000)
    summary.generation_timings_ms = timings_ms
    for day in new_days:
        await db.refresh(day)

    print(
        json.dumps(
            {
                "event": "itinerary_generation_completed",
                "generation_id": generation_id,
                "trip_id": str(trip.id),
                "planning_mode": planning_mode,
                "fallback_reason": fallback_reason,
                "candidate_count": len(candidates),
                "days_count": total_days,
                **timings_ms,
            },
            ensure_ascii=False,
        )
    )
    return new_days, summary


async def _load_user_interests(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    prefs = user.preferences_json if user else None
    if not isinstance(prefs, dict):
        return []
    interests = prefs.get("interests") or []
    return [str(item).strip().lower() for item in interests if str(item).strip()]


def _merge_unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        clean = str(item).strip()
        key = _normalize_text(clean)
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def _filter_avoided_candidates(candidates: list[dict], avoid_places: list[str]) -> list[dict]:
    if not avoid_places:
        return candidates

    avoid_keys = [_normalize_text(place) for place in avoid_places if place.strip()]
    filtered: list[dict] = []
    for candidate in candidates:
        name = _normalize_text(str(candidate.get("name") or ""))
        address = _normalize_text(str(candidate.get("address") or ""))
        if any(key and (key in name or key in address) for key in avoid_keys):
            continue
        filtered.append(candidate)
    return filtered


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").replace("đ", "d")


def _sanitize_itinerary(data: dict, total_days: int, candidates_by_ref: dict[str, dict]) -> dict:
    raw_days = data.get("days") if isinstance(data, dict) else []
    days_by_number: dict[int, list[dict]] = {}
    if isinstance(raw_days, list):
        for raw_day in raw_days:
            if not isinstance(raw_day, dict):
                continue
            try:
                day_number = int(raw_day.get("day_number"))
            except (TypeError, ValueError):
                continue
            if not 1 <= day_number <= total_days:
                continue
            activities = raw_day.get("activities") or []
            if not isinstance(activities, list):
                activities = []
            days_by_number[day_number] = [
                _sanitize_activity(a, candidates_by_ref)
                for a in activities
                if isinstance(a, dict)
            ]

    return {
        "days": [
            {"day_number": day, "activities": days_by_number.get(day, [])}
            for day in range(1, total_days + 1)
        ]
    }


def _sanitize_activity(activity: dict, candidates_by_ref: dict[str, dict]) -> dict:
    location_ref = activity.get("location_ref")
    if location_ref not in candidates_by_ref:
        location_ref = None
    return {
        "title": str(activity.get("title") or "Hoat dong")[:200],
        "description": activity.get("description"),
        "type": _sanitize_type(activity.get("type")),
        "start_time": _sanitize_time(activity.get("start_time")),
        "end_time": _sanitize_time(activity.get("end_time")),
        "estimated_cost": _sanitize_cost(activity.get("estimated_cost")),
        "notes": activity.get("notes"),
        "location_ref": location_ref,
        "reason": activity.get("reason"),
        "travel_note": activity.get("travel_note"),
        "locked": bool(activity.get("locked")),
    }


def _sanitize_time(time_str) -> str | None:
    if not isinstance(time_str, str):
        return None
    time_str = time_str.strip()
    if re.match(r"^([01]\d|2[0-3]):[0-5]\d$", time_str):
        return time_str
    if re.match(r"^\d:[0-5]\d$", time_str):
        return f"0{time_str}"
    return None


def _sanitize_type(type_str) -> str:
    return type_str if type_str in ["meal", "attraction", "hotel", "transport", "other"] else "other"


def _sanitize_cost(cost) -> int | None:
    if cost is None:
        return None
    try:
        value = int(cost)
        return value if value >= 0 else None
    except (ValueError, TypeError):
        return None


def _validate_itinerary(
    data: dict,
    *,
    total_days: int,
    candidates_by_ref: dict[str, dict],
    budget: int | None,
    budget_mode: str = "flexible_15",
    payload: GenerateDaysRequest | None = None,
) -> list[str]:
    errors: list[str] = []
    days = data.get("days") if isinstance(data, dict) else []
    if not isinstance(days, list) or len(days) != total_days:
        return [f"Expected exactly {total_days} days."]

    total_cost = 0
    place_based_types = {"attraction", "meal", "hotel"}
    available_attractions = sum(
        1 for candidate in candidates_by_ref.values() if candidate.get("category") == "attraction"
    )

    for day in days:
        day_number = int(day.get("day_number") or 0)
        day_activities = [activity for activity in day.get("activities", []) if isinstance(activity, dict)]
        intervals: list[tuple[int, int]] = []
        day_types: set[str] = set()
        day_titles: list[str] = []
        day_attraction_count = 0
        latest_end = 0
        for activity in day_activities:
            activity_type = _sanitize_type(activity.get("type"))
            title = activity.get("title") or "activity"
            normalized_title = _normalize_text(str(title))
            day_types.add(activity_type)
            day_titles.append(normalized_title)
            if activity_type in place_based_types and candidates_by_ref and not activity.get("location_ref"):
                errors.append(f"Activity '{title}' needs a valid location_ref.")
            if activity.get("location_ref") and activity["location_ref"] not in candidates_by_ref:
                errors.append(f"Unknown location_ref {activity.get('location_ref')}.")
            if activity_type == "attraction":
                day_attraction_count += 1
            total_cost += _sanitize_cost(activity.get("estimated_cost")) or 0
            start = _minutes(activity.get("start_time"))
            end = _minutes(activity.get("end_time"))
            if start is None or end is None or end <= start:
                errors.append(f"Activity '{title}' has invalid time.")
                continue
            if any(start < old_end and end > old_start for old_start, old_end in intervals):
                errors.append(f"Day {day.get('day_number')} has overlapping activities.")
            intervals.append((start, end))
            latest_end = max(latest_end, end)

        if not day_activities:
            errors.append(f"Day {day_number} has no activities.")
            continue

        title_text = " ".join(day_titles)
        has_lodging = (
            "hotel" in day_types
            or any(key in title_text for key in ["homestay", "khach san", "nhan phong", "check-in", "check out", "checkout", "nghi dem"])
        )
        has_rest = any(key in title_text for key in ["nghi", "tam rua", "thu gian"]) or has_lodging
        has_return = "transport" in day_types and any(key in title_text for key in ["roi", "ve lai", "quay ve", "tro ve"])
        is_overnight_travel_day = "transport" in day_types and latest_end >= (23 * 60 + 30) and not has_lodging

        if day_number == 1 and "transport" not in day_types:
            errors.append("Day 1 needs outbound transport from the departure location.")
        if 1 < day_number < total_days and "meal" not in day_types:
            errors.append(f"Day {day_number} needs at least one meal.")
        if day_number < total_days and not has_lodging and not is_overnight_travel_day:
            errors.append(f"Day {day_number} needs lodging or overnight rest.")
        if day_number > 1 and not has_rest:
            errors.append(f"Day {day_number} needs a rest/lodging step.")
        if day_number == total_days and total_days > 1 and "meal" not in day_types:
            errors.append("Last day needs at least one meal before return.")
        if day_number == total_days and not any(key in title_text for key in ["check-out", "checkout", "tra phong"]):
            errors.append("Last day needs checkout.")
        if day_number == total_days and not has_return:
            errors.append("Last day needs return/outbound transport.")
        min_attractions = _minimum_required_attractions_for_day(
            day_number,
            total_days,
            payload or GenerateDaysRequest(),
            available_attractions,
        )
        if available_attractions and day_attraction_count < min_attractions:
            errors.append(f"Day {day_number} needs at least {min_attractions} attraction activity.")

    budget_cap = _budget_cap(budget, budget_mode)
    if budget_cap and total_cost > budget_cap:
        errors.append("Total estimated cost is over the selected budget cap.")

    if payload:
        required_matches = {
            _normalize_text(str(candidate.get("must_visit_match")))
            for candidate in candidates_by_ref.values()
            if candidate.get("must_visit_match")
        }
        included_matches = {
            _normalize_text(str(candidates_by_ref.get(activity.get("location_ref"), {}).get("must_visit_match")))
            for day in days
            for activity in day.get("activities", [])
            if activity.get("location_ref")
            and candidates_by_ref.get(activity.get("location_ref"), {}).get("must_visit_match")
        }
        for missing_match in sorted(required_matches - included_matches):
            errors.append(f"MUST_VISIT_MISSING: Required place '{missing_match}' is not scheduled.")

    return errors[:12]


def _minutes(value: str | None) -> int | None:
    value = _sanitize_time(value)
    if not value:
        return None
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _format_minutes(value: int) -> str:
    value = value % (24 * 60)
    return f"{value // 60:02d}:{value % 60:02d}"


def _safe_time_window(start: int, duration: int, *, latest_end: int = 23 * 60 + 59) -> tuple[str, str] | None:
    end = min(start + max(duration, 1), latest_end)
    if end <= start:
        return None
    return _format_minutes(start), _format_minutes(end)


def _arrival_plan(payload: GenerateDaysRequest) -> tuple[int, int, int, int]:
    departure_min = _minutes(payload.departure_time) if payload.departure_time else None
    if departure_min is None:
        departure_min = 6 * 60 + 30

    if payload.estimated_travel_hours is not None:
        travel_minutes = max(int(round(payload.estimated_travel_hours * 60)), 0)
    else:
        travel_minutes = 5 * 60
    if travel_minutes == 0:
        travel_minutes = 15

    arrival_total = departure_min + travel_minutes
    return departure_min, travel_minutes, arrival_total // (24 * 60), arrival_total % (24 * 60)


def _enforce_closed_loop_itinerary(
    data: dict,
    trip: Trip,
    candidates: list[dict],
    total_days: int,
    payload: GenerateDaysRequest,
) -> None:
    """Add deterministic travel/lodging/meals/rest/return steps for a closed-loop route."""
    days = data.get("days") if isinstance(data, dict) else []
    if not isinstance(days, list):
        return

    meals = [c for c in candidates if c.get("category") in {"restaurant", "cafe"}]
    hotels = [c for c in candidates if c.get("category") == "hotel"]
    hotel = hotels[0] if hotels else None
    traveler_count = max(trip.num_travelers or 1, 1)
    used_attraction_refs: set[str] = set()
    meal_index = 0
    departure_min, _travel_minutes, arrival_day_offset, arrival_min = _arrival_plan(payload)
    arrival_day = min(max(1 + arrival_day_offset, 1), total_days)
    departure = payload.departure_location or "diem xuat phat"
    arrival_transport = payload.arrival_transport or payload.transport_mode or "phuong tien phu hop"

    for day in days:
        day_number = int(day.get("day_number") or 0)
        if not 1 <= day_number <= total_days:
            continue

        acts = [a for a in day.get("activities", []) if isinstance(a, dict)]
        acts = _drop_repeated_attractions(acts, used_attraction_refs)
        earliest_daily_min = 0

        if day_number < arrival_day:
            acts = []
        elif day_number == arrival_day:
            ready_min = min(arrival_min + 45, 23 * 60 + 59)
            earliest_daily_min = ready_min
            acts = [
                a for a in acts
                if (_minutes(a.get("start_time")) or 0) >= ready_min
                or _sanitize_type(a.get("type")) in {"hotel", "transport"}
            ]
        elif day_number == 1:
            acts = [
                a for a in acts
                if (_minutes(a.get("start_time")) or 0) >= 720 or _sanitize_type(a.get("type")) in {"meal", "hotel"}
            ]

        if day_number == 1:
            travel_end = arrival_min if arrival_day == 1 else 23 * 60 + 59
            if travel_end <= departure_min:
                travel_end = min(departure_min + 15, 23 * 60 + 59)
            _append_activity(
                acts,
                _simple_activity(
                    f"Di chuyen tu {departure} den {trip.destination} bang {arrival_transport}",
                    "transport",
                    _format_minutes(departure_min),
                    _format_minutes(travel_end),
                    _estimate_arrival_transport_cost(trip, payload),
                    None,
                    "Tinh ca chi phi di chuyen lien tinh/den diem du lich cho ca nhom.",
                ),
            )

        if 1 < day_number < arrival_day:
            _append_activity(
                acts,
                _simple_activity(
                    f"Tiep tuc di chuyen den {trip.destination}",
                    "transport",
                    "00:00",
                    "23:59",
                    0,
                    None,
                    "Chang di chuyen keo dai qua ngay, duoc tach de khong tao gio ket thuc nho hon gio bat dau.",
                ),
            )

        if day_number == arrival_day:
            if arrival_day > 1 and arrival_min > 0:
                _append_activity(
                    acts,
                    _simple_activity(
                        f"Tiep tuc di chuyen den {trip.destination}",
                        "transport",
                        "00:00",
                        _format_minutes(arrival_min),
                        0,
                        None,
                        "Phan di chuyen sau nua dem, tach rieng khoi ngay xuat phat.",
                    ),
                )

            checkin_window = _safe_time_window(arrival_min, 30)
            if checkin_window:
                checkin_start, checkin_end = checkin_window
            else:
                checkin_start, checkin_end = "11:45", "12:15"
            _append_activity(
                acts,
                _candidate_activity(
                    hotel,
                    fallback_title=f"Nhan phong homestay/khach san tai {trip.destination}",
                    activity_type="hotel" if hotel else "other",
                    start=checkin_start,
                    end=checkin_end,
                    cost=0,
                    notes="Den noi, gui hanh ly/nhan phong neu co san phong va nghi ngan truoc khi bat dau lich choi.",
                ),
            )
        elif arrival_day < day_number < total_days:
            _append_activity(
                acts,
                _candidate_activity(
                    hotel,
                    fallback_title=f"Xuat phat tu homestay tai {trip.destination}",
                    activity_type="hotel" if hotel else "other",
                    start="07:30",
                    end="07:45",
                    cost=0,
                    notes="Bat dau ngay moi tu noi luu tru de lo trinh ro rang.",
                ),
            )

        if day_number == total_days:
            acts = [
                a for a in acts
                if (_minutes(a.get("start_time")) or 0) < 1020 or _sanitize_type(a.get("type")) in {"transport", "hotel"}
            ]

        if day_number >= arrival_day:
            breakfast = _next_candidate(meals, meal_index)
            meal_index += 1
            if (_minutes("08:45") or 0) > earliest_daily_min:
                _append_meal_if_missing(acts, breakfast, trip.destination, "sang", "08:00", "08:45", 50_000 * traveler_count)

            lunch = _next_candidate(meals, meal_index)
            meal_index += 1
            if (_minutes("13:15") or 0) > earliest_daily_min:
                _append_meal_if_missing(acts, lunch, trip.destination, "trua", "12:15", "13:15", 120_000 * traveler_count)
                _append_activity(
                    acts,
                    _simple_activity(
                        "Nghi ngoi tai homestay/quan ca phe gan tuyen",
                        "other",
                        "13:15",
                        "14:00",
                        0,
                        None,
                        "Giu suc va tranh lich bi day qua muc.",
                    ),
                )

            dinner = _next_candidate(meals, meal_index)
            meal_index += 1
            if (_minutes("19:30") or 0) > earliest_daily_min:
                _append_meal_if_missing(acts, dinner, trip.destination, "toi", "18:30", "19:30", 150_000 * traveler_count)

        if arrival_day <= day_number < total_days:
            _append_activity(
                acts,
                _candidate_activity(
                    hotel,
                    fallback_title=f"Ve homestay nghi ngoi, tam rua va nghi dem tai {trip.destination}",
                    activity_type="hotel" if hotel else "other",
                    start="21:00",
                    end="21:30",
                    cost=_estimate_lodging_cost(trip),
                    notes="Ket thuc ngay tai noi luu tru, phu hop lich trinh khep kin.",
                ),
            )
        elif day_number == total_days:
            _append_activity(
                acts,
                _candidate_activity(
                    hotel,
                    fallback_title=f"Check-out homestay/khach san tai {trip.destination}",
                    activity_type="hotel" if hotel else "other",
                    start="16:30",
                    end="17:00",
                    cost=0,
                    notes="Kiem tra hanh ly va hoan tat tra phong.",
                ),
            )
            _append_activity(
                acts,
                _simple_activity(
                    f"Di chuyen roi {trip.destination} ve lai diem xuat phat",
                    "transport",
                    "19:45",
                    "23:30",
                    _estimate_arrival_transport_cost(trip, payload),
                    None,
                    "Tinh chi phi quay ve/roi diem du lich cho ca nhom.",
                ),
            )

        day["activities"] = _sort_and_trim_overlaps(acts)


def _enrich_experience_route(
    data: dict,
    trip: Trip,
    candidates: list[dict],
    total_days: int,
    payload: GenerateDaysRequest,
) -> list[str]:
    """Fill realistic sightseeing/cafe slots using candidate distance clusters."""
    days = data.get("days") if isinstance(data, dict) else []
    if not isinstance(days, list):
        return []

    attractions = [
        candidate for candidate in candidates
        if candidate.get("category") == "attraction" and candidate.get("ref")
    ]
    cafes = [
        candidate for candidate in candidates
        if candidate.get("category") == "cafe" and candidate.get("ref")
    ]
    if not attractions:
        return ["Khong co du lieu diem tham quan phu hop de chen them trai nghiem trong lich trinh."]

    traveler_count = max(trip.num_travelers or 1, 1)
    destination_profile = build_destination_profile(trip.destination, candidates)
    is_mountain_corridor = destination_profile["topology"] == "mountain_corridor"
    used_refs = {
        activity.get("location_ref")
        for day in days
        for activity in day.get("activities", [])
        if _sanitize_type(activity.get("type")) == "attraction" and activity.get("location_ref")
    }
    attractions_by_ref = {candidate["ref"]: candidate for candidate in attractions}
    attraction_family_counts: dict[str, int] = {}
    for day in days:
        for activity in day.get("activities", []):
            candidate = attractions_by_ref.get(activity.get("location_ref"))
            if candidate:
                family = _attraction_family(candidate)
                attraction_family_counts[family] = attraction_family_counts.get(family, 0) + 1
    warnings: list[str] = []

    for day in days:
        day_number = int(day.get("day_number") or 0)
        if not 1 <= day_number <= total_days:
            continue

        acts = [activity for activity in day.get("activities", []) if isinstance(activity, dict)]
        slots = _experience_slots_for_day(day_number, total_days, payload)
        if not slots:
            continue

        existing_count = sum(1 for activity in acts if _sanitize_type(activity.get("type")) == "attraction")
        target = _target_attractions_for_day(day_number, total_days, payload, len(attractions))
        if (
            is_mountain_corridor
            and payload.accept_long_daily_travel
            and payload.pace == "packed"
        ):
            target = min(len(slots), len(attractions), 4)
        needed = max(target - existing_count, 0)
        if needed <= 0:
            day["activities"] = _sort_and_trim_overlaps(acts)
            continue

        available = [candidate for candidate in attractions if candidate.get("ref") not in used_refs]
        future_minimum = _future_minimum_attractions(day_number, total_days, payload, len(attractions))
        required_now = max(
            _minimum_required_attractions_for_day(day_number, total_days, payload, len(attractions)) - existing_count,
            0,
        )
        selectable_count = max(len(available) - future_minimum, required_now)
        if is_mountain_corridor and payload.accept_long_daily_travel:
            selected = _select_corridor_attractions(
                available,
                min(needed, selectable_count),
                payload.pace,
                max_daily_travel_minutes=payload.max_daily_travel_minutes,
            )
        else:
            selected = _select_clustered_attractions(
                available,
                min(needed, selectable_count),
                payload.pace,
                family_counts=attraction_family_counts,
            )
        if not selected and existing_count == 0:
            warnings.append(f"Ngay {day_number} chua co diem tham quan vi khong con candidate phu hop.")

        for slot, candidate in zip(slots, selected):
            start, end = slot
            _append_activity(
                acts,
                _candidate_activity(
                    candidate,
                    fallback_title=f"Tham quan diem noi bat tai {trip.destination}",
                    activity_type="attraction",
                    start=start,
                    end=end,
                    cost=80_000 * traveler_count,
                    notes=(
                        _corridor_note(candidate, selected)
                        if is_mountain_corridor and payload.accept_long_daily_travel
                        else _cluster_note(candidate, selected)
                    ),
                ),
            )
            used_refs.add(candidate.get("ref"))
            family = _attraction_family(candidate)
            attraction_family_counts[family] = attraction_family_counts.get(family, 0) + 1

        if day_number < total_days and payload.pace != "relaxed":
            cafe = _next_unused_candidate(cafes, used_refs)
            if cafe:
                _append_activity(
                    acts,
                    _candidate_activity(
                        cafe,
                        fallback_title=f"Cafe/di dao toi tai {trip.destination}",
                        activity_type="meal",
                        start="19:45",
                        end="20:45",
                        cost=70_000 * traveler_count,
                        notes="Hoat dong nhe buoi toi de lich trinh co them trai nghiem vui choi nhung van ve homestay nghi som.",
                    ),
                )

        day["activities"] = _sort_and_trim_overlaps(acts)

    return _merge_unique(warnings)


def _lock_required_visits(
    data: dict,
    trip: Trip,
    candidates: list[dict],
    total_days: int,
    payload: GenerateDaysRequest,
) -> list[str]:
    """Guarantee resolved required places survive AI, fallback and later optional filling."""
    days = data.get("days") if isinstance(data, dict) else []
    if not isinstance(days, list):
        return ["MUST_VISIT_MISSING: Khong co cau truc ngay de khoa diem bat buoc."]

    required = [
        candidate
        for candidate in sorted(candidates, key=_candidate_priority_key)
        if candidate.get("must_visit_match") and candidate.get("ref")
    ]
    if not required:
        return []

    item_by_name = {
        _normalize_text(item.name): item
        for item in payload.must_visit_items
        if item.priority == "required"
    }
    warnings: list[str] = []
    used_refs = {
        activity.get("location_ref")
        for day in days
        for activity in day.get("activities", [])
        if activity.get("location_ref")
    }

    for candidate in required:
        ref = candidate["ref"]
        if ref in used_refs:
            for day in days:
                for activity in day.get("activities", []):
                    if activity.get("location_ref") == ref:
                        activity["locked"] = True
                        activity["title"] = _required_activity_title(candidate)
                        activity["notes"] = _locked_note(activity.get("notes"))
            continue

        match_name = str(candidate.get("must_visit_match") or candidate.get("name") or "")
        request_item = item_by_name.get(_normalize_text(match_name))
        preferred_day = request_item.preferred_day if request_item else None
        day_order = sorted(
            days,
            key=lambda day: (
                0 if preferred_day and int(day.get("day_number") or 0) == preferred_day else 1,
                int(day.get("day_number") or 0),
            ),
        )
        placed = False
        for day in day_order:
            day_number = int(day.get("day_number") or 0)
            if not 1 <= day_number <= total_days:
                continue
            activities = [activity for activity in day.get("activities", []) if isinstance(activity, dict)]
            for start, end in _experience_slots_for_day(day_number, total_days, payload):
                slot_start = _minutes(start) or 0
                slot_end = _minutes(end) or 0
                conflicts = [
                    activity
                    for activity in activities
                    if _activity_overlaps(activity, slot_start, slot_end)
                ]
                if any(
                    _sanitize_type(activity.get("type")) != "attraction"
                    or activity.get("locked")
                    or (
                        activity.get("location_ref")
                        and next(
                            (
                                candidate_item.get("must_visit_match")
                                for candidate_item in candidates
                                if candidate_item.get("ref") == activity.get("location_ref")
                            ),
                            None,
                        )
                    )
                    for activity in conflicts
                ):
                    continue
                for conflict in conflicts:
                    activities.remove(conflict)
                activity_type = (
                    "meal"
                    if candidate.get("category") in {"restaurant", "cafe"}
                    else "hotel"
                    if candidate.get("category") == "hotel"
                    else "attraction"
                )
                locked_activity = _candidate_activity(
                    candidate,
                    fallback_title=match_name,
                    activity_type=activity_type,
                    start=start,
                    end=end,
                    cost=80_000 * max(trip.num_travelers or 1, 1),
                    notes=_locked_note(
                        "Dia diem bat buoc duoc khoa truoc khi them cac goi y tuy chon."
                    ),
                )
                locked_activity["locked"] = True
                locked_activity["title"] = _required_activity_title(candidate)
                activities.append(locked_activity)
                day["activities"] = _sort_and_trim_overlaps(activities)
                used_refs.add(ref)
                placed = True
                break
            if placed:
                break
        if not placed:
            warnings.append(
                f"MUST_VISIT_MISSING: Khong con khung gio kha thi cho {match_name}."
            )
    return warnings


def _locked_note(existing: str | None) -> str:
    marker = "[BAT BUOC THEO YEU CAU NGUOI DUNG]"
    return f"{marker} {existing or ''}".strip()


def _required_activity_title(candidate: dict) -> str:
    name = str(candidate.get("name") or "Địa điểm bắt buộc")
    match = _normalize_text(str(candidate.get("must_visit_match") or ""))
    if "cau vang" in match and "ba na hills" in _normalize_text(name):
        return f"Check-in Cầu Vàng tại {name}"
    return name


def _experience_slots_for_day(
    day_number: int,
    total_days: int,
    payload: GenerateDaysRequest,
) -> list[tuple[str, str]]:
    departure_min, _travel_minutes, arrival_day_offset, arrival_min = _arrival_plan(payload)
    del departure_min
    arrival_day = min(max(1 + arrival_day_offset, 1), total_days)
    if day_number < arrival_day:
        return []

    earliest = 0
    if day_number == arrival_day:
        earliest = min(arrival_min + 45, 23 * 60 + 59)
    latest = 20 * 60 + 45
    if day_number == total_days:
        latest = 16 * 60 + 30

    if latest - earliest < 90:
        return []

    base_slots = [
        ("09:15", "10:45"),
        ("10:55", "12:05"),
        ("14:10", "15:40"),
        ("15:50", "17:20"),
    ]
    return [
        (start, end)
        for start, end in base_slots
        if (_minutes(start) or 0) >= earliest and (_minutes(end) or 0) <= latest
    ]


def _target_attractions_for_day(
    day_number: int,
    total_days: int,
    payload: GenerateDaysRequest,
    available_attractions: int,
) -> int:
    slots = _experience_slots_for_day(day_number, total_days, payload)
    if not slots or available_attractions <= 0:
        return 0

    if payload.pace == "relaxed":
        target = 1
    elif payload.pace == "packed":
        target = 3
    else:
        target = 3 if len(slots) >= 3 else 2

    return min(target, len(slots), available_attractions)


def _minimum_required_attractions_for_day(
    day_number: int,
    total_days: int,
    payload: GenerateDaysRequest,
    available_attractions: int,
) -> int:
    slots = _experience_slots_for_day(day_number, total_days, payload)
    if not slots or available_attractions <= 0:
        return 0
    if day_number == total_days:
        return 1
    if len(slots) >= 3 and payload.pace in {"balanced", "packed"} and available_attractions >= 2:
        return 2
    return 1


def _future_minimum_attractions(
    current_day: int,
    total_days: int,
    payload: GenerateDaysRequest,
    available_attractions: int,
) -> int:
    return sum(
        _minimum_required_attractions_for_day(day_number, total_days, payload, available_attractions)
        for day_number in range(current_day + 1, total_days + 1)
    )


def _select_clustered_attractions(
    candidates: list[dict],
    target: int,
    pace: str,
    *,
    family_counts: dict[str, int] | None = None,
) -> list[dict]:
    if target <= 0 or not candidates:
        return []

    family_counts = family_counts or {}
    sorted_candidates = sorted(
        candidates,
        key=lambda candidate: (
            0 if candidate.get("must_visit_match") else 1,
            family_counts.get(_attraction_family(candidate), 0),
            _candidate_priority_key(candidate),
        ),
    )
    anchor = sorted_candidates[0]
    if target == 1:
        return [anchor]

    with_distance = [
        (candidate, _candidate_distance_meters(anchor, candidate))
        for candidate in sorted_candidates[1:]
    ]
    with_distance.sort(key=lambda item: (item[1] if item[1] is not None else 10_000_000, _candidate_priority_key(item[0])))
    nearest_distance = next((distance for _candidate, distance in with_distance if distance is not None), None)

    if nearest_distance is None:
        max_count = min(target, 2)
        limit = None
    elif nearest_distance <= 3_000:
        max_count = target if pace != "relaxed" else min(target, 2)
        limit = 3_000
    elif nearest_distance <= 8_000:
        max_count = min(target, 2)
        limit = 8_000
    else:
        max_count = 1
        limit = None

    selected = [anchor]
    for candidate, distance in with_distance:
        if len(selected) >= max_count:
            break
        if limit is not None and (distance is None or distance > limit):
            continue
        selected.append(candidate)
    return selected


def _attraction_family(candidate: dict) -> str:
    searchable = _normalize_text(
        " ".join(
            [
                str(candidate.get("name") or ""),
                " ".join(str(tag) for tag in candidate.get("tags") or []),
            ]
        )
    )
    families = (
        ("beach", ("bien", "bai tam")),
        ("mountain_viewpoint", ("nui", "doi", "dinh", "viewpoint", "scenic")),
        ("culture_history", ("bao tang", "di tich", "lich su", "lang", "tuong niem")),
        ("spiritual", ("chua", "den", "nha tho", "thanh duong")),
        ("market_local_life", ("cho", "lang chai", "pho co", "local")),
        ("architecture_bridge", ("cau", "architecture", "landmark")),
        ("park_entertainment", ("cong vien", "theme park", "entertainment")),
        ("nature", ("thac", "ho", "suoi", "hang", "nature")),
    )
    return next(
        (family for family, keywords in families if any(keyword in searchable for keyword in keywords)),
        "other",
    )


def _select_corridor_attractions(
    candidates: list[dict],
    target: int,
    pace: str,
    *,
    max_daily_travel_minutes: int = 240,
) -> list[dict]:
    """Build a forward route with short stops instead of a compact urban radius."""
    if target <= 0 or not candidates:
        return []

    remaining = sorted(candidates, key=_candidate_priority_key)
    selected = [remaining.pop(0)]
    max_leg_meters = 45_000 if pace == "packed" else 35_000
    estimated_travel_minutes = 0
    while remaining and len(selected) < target:
        current = selected[-1]
        ranked = sorted(
            remaining,
            key=lambda candidate: (
                _candidate_distance_meters(current, candidate)
                if _candidate_distance_meters(current, candidate) is not None
                else 10_000_000,
                _candidate_priority_key(candidate),
            ),
        )
        next_candidate = ranked[0]
        distance = _candidate_distance_meters(current, next_candidate)
        if distance is not None and distance > max_leg_meters and not next_candidate.get("must_visit_match"):
            break
        leg_minutes = round((distance or 0) / 500)
        if (
            estimated_travel_minutes + leg_minutes > max_daily_travel_minutes
            and not next_candidate.get("must_visit_match")
        ):
            break
        selected.append(next_candidate)
        remaining.remove(next_candidate)
        estimated_travel_minutes += leg_minutes
    return selected


def _candidate_priority_key(candidate: dict) -> tuple[int, float, int, int, str]:
    return (
        0 if candidate.get("must_visit_match") else 1,
        -float(candidate.get("score") or 0),
        0 if candidate.get("rating") else 1,
        0 if candidate.get("photo_url") else 1,
        _normalize_text(str(candidate.get("name") or "")),
    )


def _candidate_distance_meters(first: dict, second: dict) -> float | None:
    try:
        lat1 = float(first["lat"])
        lng1 = float(first["lng"])
        lat2 = float(second["lat"])
        lng2 = float(second["lng"])
    except (KeyError, TypeError, ValueError):
        return None
    return _haversine_meters(lat1, lng1, lat2, lng2)


def _has_long_required_leg(
    candidates: list[dict],
    *,
    minimum_meters: float,
) -> bool:
    for index, candidate in enumerate(candidates):
        for other in candidates[index + 1:]:
            distance = _candidate_distance_meters(candidate, other)
            if distance is not None and distance >= minimum_meters:
                return True
    return False


def _haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _cluster_note(candidate: dict, selected: list[dict]) -> str:
    if len(selected) <= 1:
        return "Diem tham quan chinh trong ngay, giu lich trinh thong thoang."
    distances = [
        _candidate_distance_meters(candidate, other)
        for other in selected
        if other is not candidate
    ]
    nearest = min((distance for distance in distances if distance is not None), default=None)
    if nearest is not None and nearest <= 3_000:
        return "Nam trong cum diem gan nhau nen co the ghep 2-3 diem trong cung ngay."
    if nearest is not None and nearest <= 8_000:
        return "Khoang cach vua phai, chi ghep it diem de tranh lich qua day."
    return "Duoc chon theo do uu tien, can can doi thoi gian di chuyen."


def _corridor_note(candidate: dict, selected: list[dict]) -> str:
    if candidate.get("must_visit_match"):
        return _locked_note("Diem neo chinh cua cung duong mien nui.")
    return "Diem dung nam tren cung duong mien nui, uu tien han che quay dau va di vong."


def _next_unused_candidate(candidates: list[dict], used_refs: set[str | None]) -> dict | None:
    for candidate in sorted(candidates, key=_candidate_priority_key):
        ref = candidate.get("ref")
        if ref and ref not in used_refs:
            used_refs.add(ref)
            return candidate
    return None


def _drop_repeated_attractions(activities: list[dict], used_refs: set[str]) -> list[dict]:
    result: list[dict] = []
    for activity in activities:
        ref = activity.get("location_ref")
        if _sanitize_type(activity.get("type")) == "attraction" and ref:
            if ref in used_refs:
                continue
            used_refs.add(ref)
        result.append(activity)
    return result


_MEAL_FAMILY_KEYWORDS = (
    "banh trang cuon thit heo",
    "mi quang",
    "cao lau",
    "bun cha",
    "bun bo",
    "bun rieu",
    "pho",
    "com ga",
    "com tam",
    "banh mi",
    "hai san",
    "lau",
    "nem lui",
    "banh xeo",
    "ca phe",
)


def _meal_family(candidate: dict) -> str:
    searchable = _normalize_text(
        " ".join(
            [
                str(candidate.get("name") or ""),
                " ".join(str(tag) for tag in candidate.get("tags") or []),
            ]
        )
    )
    return next(
        (keyword for keyword in _MEAL_FAMILY_KEYWORDS if keyword in searchable),
        _normalize_text(str(candidate.get("name") or "")),
    )


def _diversify_meals(
    data: dict,
    candidates_by_ref: dict[str, dict],
    *,
    max_family_repeats: int = 2,
) -> list[str]:
    """Cap repeated dishes/venues while preserving locked user requirements."""
    meal_candidates = sorted(
        (
            candidate
            for candidate in candidates_by_ref.values()
            if candidate.get("category") in {"restaurant", "cafe"}
            and candidate.get("ref")
            and not candidate.get("must_visit_match")
        ),
        key=_candidate_priority_key,
    )
    used_refs: set[str] = set()
    family_counts: dict[str, int] = {}
    replacements = 0

    for day in data.get("days", []):
        for activity in day.get("activities", []):
            if _sanitize_type(activity.get("type")) != "meal":
                continue
            ref = activity.get("location_ref")
            candidate = candidates_by_ref.get(ref) if ref else None
            if not candidate:
                continue
            family = _meal_family(candidate)
            is_locked = bool(activity.get("locked") or candidate.get("must_visit_match"))
            repeated = ref in used_refs or family_counts.get(family, 0) >= max_family_repeats
            if repeated and not is_locked:
                replacement = next(
                    (
                        option
                        for option in meal_candidates
                        if option["ref"] not in used_refs
                        and family_counts.get(_meal_family(option), 0) < max_family_repeats
                    ),
                    None,
                )
                if replacement:
                    activity["title"] = replacement["name"]
                    activity["description"] = replacement.get("address")
                    activity["location_ref"] = replacement["ref"]
                    activity["reason"] = (
                        "Đổi món và địa điểm để trải nghiệm ẩm thực địa phương đa dạng hơn."
                    )
                    activity["notes"] = (
                        "Món người dùng yêu cầu được giới hạn 1-2 bữa; "
                        "bữa này dùng một đặc sản khác."
                    )
                    candidate = replacement
                    ref = replacement["ref"]
                    family = _meal_family(replacement)
                    replacements += 1
            used_refs.add(str(ref))
            family_counts[family] = family_counts.get(family, 0) + 1

    if not replacements:
        return []
    return [
        f"Đã thay {replacements} bữa ăn bị trùng để tăng độ đa dạng đặc sản và quán ăn."
    ]


def _append_meal_if_missing(
    activities: list[dict],
    candidate: dict | None,
    destination: str,
    meal_name: str,
    start: str,
    end: str,
    cost: int,
) -> None:
    slot_start = _minutes(start) or 0
    slot_end = _minutes(end) or 0
    has_meal = any(
        _sanitize_type(a.get("type")) == "meal"
        and _activity_overlaps(a, slot_start - 45, slot_end + 45)
        for a in activities
    )
    if has_meal:
        return
    _append_activity(
        activities,
        _candidate_activity(
            candidate,
            fallback_title=f"An {meal_name} tai {destination}",
            activity_type="meal",
            start=start,
            end=end,
            cost=cost,
        ),
    )


def _append_activity(activities: list[dict], activity: dict) -> None:
    start = _minutes(activity.get("start_time"))
    end = _minutes(activity.get("end_time"))
    if start is not None and end is not None:
        for existing in activities:
            existing_start = _minutes(existing.get("start_time"))
            existing_end = _minutes(existing.get("end_time"))
            if existing_start is None or existing_end is None:
                continue
            if start < existing_end and end > existing_start:
                return

    title_key = _normalize_text(str(activity.get("title") or ""))
    if title_key and any(_normalize_text(str(a.get("title") or "")) == title_key for a in activities):
        return
    activities.append(activity)


def _activity_overlaps(activity: dict, start: int, end: int) -> bool:
    activity_start = _minutes(activity.get("start_time"))
    activity_end = _minutes(activity.get("end_time"))
    if activity_start is None or activity_end is None:
        return False
    return activity_start < end and activity_end > start


def _sort_and_trim_overlaps(activities: list[dict]) -> list[dict]:
    sorted_acts = sorted(
        activities,
        key=lambda item: (_minutes(item.get("start_time")) if _minutes(item.get("start_time")) is not None else 9999),
    )
    result: list[dict] = []
    intervals: list[tuple[int, int]] = []
    for activity in sorted_acts:
        start = _minutes(activity.get("start_time"))
        end = _minutes(activity.get("end_time"))
        if start is None or end is None or end <= start:
            continue
        if any(start < old_end and end > old_start for old_start, old_end in intervals):
            continue
        intervals.append((start, end))
        result.append(activity)
    return result


def _estimate_arrival_transport_cost(trip: Trip, payload: GenerateDaysRequest) -> int:
    traveler_count = max(trip.num_travelers or 1, 1)
    text = _normalize_text(f"{payload.arrival_transport or ''} {payload.transport_mode or ''}")
    if "may bay" in text or "flight" in text:
        return 1_200_000 * traveler_count
    if "o to" in text or "car" in text:
        return 350_000 * traveler_count
    if "xe may" in text or "motorbike" in text:
        return 180_000 * traveler_count
    if "tau" in text:
        return 350_000 * traveler_count
    return 250_000 * traveler_count


def _estimate_lodging_cost(trip: Trip) -> int:
    traveler_count = max(trip.num_travelers or 1, 1)
    rooms = max((traveler_count + 1) // 2, 1)
    return 250_000 * rooms


def _build_fallback_itinerary(trip: Trip, candidates: list[dict], *, total_days: int, pace: str) -> dict:
    attractions = [c for c in candidates if c.get("category") == "attraction"]
    meals = [c for c in candidates if c.get("category") in {"restaurant", "cafe"}]
    hotels = [c for c in candidates if c.get("category") == "hotel"]
    activities_per_day = 1 if pace == "relaxed" else 2 if pace == "balanced" else 3
    traveler_count = max(trip.num_travelers or 1, 1)
    hotel = hotels[0] if hotels else None

    days = []
    attraction_index = 0
    meal_index = 0

    for day_number in range(1, total_days + 1):
        acts: list[dict] = []
        if day_number == 1:
            acts.append(_simple_activity("Di chuyen den khach san", "transport", "07:30", "08:15", 120000, None))

        breakfast = _next_candidate(meals, meal_index)
        meal_index += 1
        acts.append(
            _candidate_activity(
                breakfast,
                fallback_title=f"An sang tai {trip.destination}",
                activity_type="meal",
                start="08:30",
                end="09:15",
                cost=50_000 * traveler_count,
            )
        )

        slots = [("09:30", "11:30"), ("14:00", "16:00"), ("16:30", "18:00")]
        for start, end in slots[:activities_per_day]:
            attraction = _next_candidate(attractions, attraction_index)
            attraction_index += 1
            acts.append(
                _candidate_activity(
                    attraction,
                    fallback_title=f"Tham quan diem noi bat tai {trip.destination}",
                    activity_type="attraction",
                    start=start,
                    end=end,
                    cost=80_000 * traveler_count,
                )
            )

        lunch = _next_candidate(meals, meal_index)
        meal_index += 1
        acts.insert(
            min(3, len(acts)),
            _candidate_activity(
                lunch,
                fallback_title=f"An trua dac san tai {trip.destination}",
                activity_type="meal",
                start="12:00",
                end="13:00",
                cost=120_000 * traveler_count,
            ),
        )

        dinner = _next_candidate(meals, meal_index)
        meal_index += 1
        acts.append(
            _candidate_activity(
                dinner,
                fallback_title=f"An toi tai {trip.destination}",
                activity_type="meal",
                start="18:30",
                end="19:45",
                cost=150_000 * traveler_count,
            )
        )
        acts.append(
            _candidate_activity(
                hotel,
                fallback_title=f"Nghi dem tai {trip.destination}",
                activity_type="hotel",
                start="21:00",
                end="21:30",
                cost=0,
            )
        )
        if day_number == total_days:
            acts.append(_simple_activity("Check-out va di chuyen ve", "transport", "21:30", "22:00", 120000, None))

        days.append({"day_number": day_number, "activities": acts})

    data = {"days": days}
    _fit_itinerary_to_budget(data, trip.budget)
    return data


def _next_candidate(items: list[dict], index: int) -> dict | None:
    if not items:
        return None
    return items[index % len(items)]


def _candidate_activity(
    candidate: dict | None,
    *,
    fallback_title: str,
    activity_type: str,
    start: str,
    end: str,
    cost: int,
    notes: str | None = None,
) -> dict:
    title = candidate["name"] if candidate else fallback_title
    return {
        "title": title,
        "description": candidate.get("address") if candidate else None,
        "type": activity_type,
        "start_time": start,
        "end_time": end,
        "estimated_cost": cost,
        "location_ref": candidate.get("ref") if candidate else None,
        "reason": "Phu hop voi lich trinh va du lieu dia diem thuc te." if candidate else None,
        "travel_note": "Da sap xep theo khung gio can bang.",
        "notes": notes,
    }


def _simple_activity(
    title: str,
    activity_type: str,
    start: str,
    end: str,
    cost: int,
    location_ref: str | None,
    notes: str | None = None,
) -> dict:
    return {
        "title": title,
        "description": None,
        "type": activity_type,
        "start_time": start,
        "end_time": end,
        "estimated_cost": cost,
        "location_ref": location_ref,
        "reason": None,
        "travel_note": None,
        "notes": notes,
    }


def _apply_realistic_costs(data: dict, trip: Trip, budget_mode: str) -> None:
    traveler_count = max(trip.num_travelers or 1, 1)
    lodging_cost = _estimate_lodging_cost(trip)

    for day in data.get("days", []):
        for activity in day.get("activities", []):
            activity_type = _sanitize_type(activity.get("type"))
            title = _normalize_text(str(activity.get("title") or ""))
            current = _sanitize_cost(activity.get("estimated_cost")) or 0
            start_minutes = _minutes(activity.get("start_time")) or 0
            floor = 0

            if activity_type == "meal":
                if start_minutes < 600:
                    floor = 50_000 * traveler_count
                elif start_minutes < 900:
                    floor = 120_000 * traveler_count
                else:
                    floor = 150_000 * traveler_count
            elif activity_type == "transport":
                if any(key in title for key in ["den", "roi", "ve lai", "xuat phat"]):
                    floor = max(current, 250_000 * traveler_count)
                else:
                    floor = 80_000 * traveler_count
            elif activity_type == "hotel":
                if any(key in title for key in ["nghi dem", "homestay", "khach san"]):
                    floor = lodging_cost
            elif activity_type == "attraction":
                floor = 30_000 * traveler_count
            elif "du phong" in title or "buffer" in title:
                floor = 50_000 * traveler_count

            if floor and current < floor:
                activity["estimated_cost"] = floor


def _apply_grounded_candidate_costs(
    data: dict,
    trip: Trip,
    candidates_by_ref: dict[str, dict],
    budget_mode: str,
) -> None:
    """Recalculate place costs from dataset price facts instead of trusting AI."""
    travelers = max(trip.num_travelers or 1, 1)
    rooms = max(1, math.ceil(travelers / 2))
    charged_lodging: set[tuple[int, str]] = set()

    for day in data.get("days", []):
        day_number = int(day.get("day_number") or 0)
        for activity in day.get("activities", []):
            ref = activity.get("location_ref")
            candidate = candidates_by_ref.get(ref) if ref else None
            price = candidate.get("price") if candidate else None
            if not isinstance(price, dict):
                continue
            try:
                minimum = max(0, int(price.get("min_vnd") or 0))
                maximum = max(minimum, int(price.get("max_vnd") or minimum))
            except (TypeError, ValueError):
                continue
            if maximum <= 0:
                activity["estimated_cost"] = 0
                continue

            if budget_mode == "strict":
                base = minimum
            elif budget_mode == "comfort":
                base = round(minimum + (maximum - minimum) * 0.7)
            else:
                base = round((minimum + maximum) / 2)

            unit = str(price.get("unit") or "").lower()
            if unit in {"per_person", "per_guest", "per_ticket"}:
                grounded_cost = base * travelers
            elif unit in {"per_room", "per_room_per_night", "per_night"}:
                grounded_cost = base * rooms
            else:
                grounded_cost = base

            if _sanitize_type(activity.get("type")) == "hotel" and ref:
                lodging_key = (day_number, ref)
                if lodging_key in charged_lodging:
                    grounded_cost = 0
                else:
                    charged_lodging.add(lodging_key)
            activity["estimated_cost"] = grounded_cost


def _budget_cap(budget: int | None, budget_mode: str = "flexible_15") -> int | None:
    if not budget:
        return None
    if budget_mode == "strict":
        return int(budget)
    if budget_mode == "comfort":
        return int(budget * 1.3)
    return int(budget * 1.15)


def _fit_itinerary_to_budget(data: dict, budget: int | None, budget_mode: str = "flexible_15") -> None:
    cap = _budget_cap(budget, budget_mode)
    if not cap:
        return
    total = sum(
        _sanitize_cost(activity.get("estimated_cost")) or 0
        for day in data.get("days", [])
        for activity in day.get("activities", [])
    )
    if total <= cap or total <= 0:
        return
    ratio = cap / total
    for day in data.get("days", []):
        for activity in day.get("activities", []):
            cost = _sanitize_cost(activity.get("estimated_cost")) or 0
            if cost > 0:
                activity["estimated_cost"] = int(cost * ratio)


def _trim_optional_experiences_to_budget(
    data: dict,
    budget: int | None,
    budget_mode: str,
    candidates_by_ref: dict[str, dict],
    payload: GenerateDaysRequest,
) -> str | None:
    cap = _budget_cap(budget, budget_mode)
    if budget_mode != "strict" or not cap:
        return None

    def total_cost() -> int:
        return sum(
            _sanitize_cost(activity.get("estimated_cost")) or 0
            for day in data.get("days", [])
            for activity in day.get("activities", [])
        )

    if total_cost() <= cap:
        return None

    removed = 0
    for day in data.get("days", []):
        activities = [activity for activity in day.get("activities", []) if isinstance(activity, dict)]
        attraction_count = sum(1 for activity in activities if _sanitize_type(activity.get("type")) == "attraction")
        removable: list[dict] = []
        for activity in activities:
            activity_type = _sanitize_type(activity.get("type"))
            ref = activity.get("location_ref")
            is_must_visit = bool(candidates_by_ref.get(ref, {}).get("must_visit_match")) if ref else False
            if is_must_visit:
                continue
            if activity_type == "attraction" and attraction_count > _minimum_required_attractions_for_day(
                int(day.get("day_number") or 0),
                len(data.get("days", [])),
                payload,
                sum(1 for candidate in candidates_by_ref.values() if candidate.get("category") == "attraction"),
            ):
                removable.append(activity)
            elif activity_type == "meal" and ref and candidates_by_ref.get(ref, {}).get("category") == "cafe":
                removable.append(activity)

        removable.sort(key=lambda activity: _minutes(activity.get("start_time")) or 0, reverse=True)
        for activity in removable:
            if total_cost() <= cap:
                break
            if _sanitize_type(activity.get("type")) == "attraction":
                attraction_count -= 1
            activities.remove(activity)
            removed += 1
        day["activities"] = _sort_and_trim_overlaps(activities)
        if total_cost() <= cap:
            break

    if removed:
        return "Ngan sach strict qua chat nen he thong da rut bot diem phu/cafe toi, giu lai flow khep kin va diem uu tien."
    return None


def _build_generation_summary(
    data: dict,
    *,
    candidates_by_ref: dict[str, dict],
    must_visit: list[str],
    budget: int | None,
    budget_mode: str = "flexible_15",
    candidate_places_count: int,
    warnings: list[str],
    planning_mode: str = "grounded_v2",
    destination_topology: str | None = None,
    generation_id: str | None = None,
    generation_timings_ms: dict[str, int] | None = None,
    fallback_reason: str | None = None,
) -> ItineraryGenerationSummary:
    refs_used = {
        activity.get("location_ref")
        for day in data.get("days", [])
        for activity in day.get("activities", [])
        if activity.get("location_ref")
    }
    total_cost = sum(
        _sanitize_cost(activity.get("estimated_cost")) or 0
        for day in data.get("days", [])
        for activity in day.get("activities", [])
    )
    included: list[str] = []
    for ref in refs_used:
        match = candidates_by_ref.get(ref, {}).get("must_visit_match")
        if match:
            included.append(match)

    included = _merge_unique(included)
    included_keys = {_normalize_text(item) for item in included}
    missing = [place for place in must_visit if _normalize_text(place) not in included_keys]
    scheduled_details: dict[str, tuple[int, str | None, str | None]] = {}
    for day in data.get("days", []):
        day_number = int(day.get("day_number") or 0)
        for activity in day.get("activities", []):
            ref = activity.get("location_ref")
            match = candidates_by_ref.get(ref, {}).get("must_visit_match") if ref else None
            if match:
                scheduled_details[_normalize_text(str(match))] = (
                    day_number,
                    activity.get("start_time"),
                    str(candidates_by_ref.get(ref, {}).get("location_id") or "") or None,
                )
    coverage_items: list[UserRequestCoverageItem] = []
    for request in must_visit:
        detail = scheduled_details.get(_normalize_text(request))
        coverage_items.append(
            UserRequestCoverageItem(
                request=request,
                status="scheduled" if detail else "unresolved",
                day=detail[0] if detail else None,
                start_time=detail[1] if detail else None,
                location_id=detail[2] if detail else None,
            )
        )

    budget_limit = _budget_cap(budget, budget_mode)
    budget_percent = round((total_cost / budget) * 100) if budget else None
    summary_warnings = list(warnings)
    if missing:
        summary_warnings.append("Mot so dia diem nguoi dung muon di chua duoc dua vao lich trinh.")
    if budget_limit and total_cost > budget_limit:
        summary_warnings.append("Tong chi phi uoc tinh vuot qua gioi han ngan sach da chon.")
    if budget and total_cost < int(budget * 0.55):
        summary_warnings.append("Chi phi lich trinh dang thap hon ngan sach; co the can kiem tra lai chi phi ve xe, luu tru hoac ve tham quan.")

    used_candidates = [candidates_by_ref[ref] for ref in refs_used if ref in candidates_by_ref]
    approximate_count = sum(
        candidate.get("coordinate_status") == "approximate"
        for candidate in used_candidates
    )
    verified_count = sum(
        candidate.get("data_confidence") in {"high", "medium"}
        and candidate.get("coordinate_status") not in {"suspicious", "missing"}
        for candidate in used_candidates
    )
    versions = sorted(
        {
            str(candidate.get("dataset_version"))
            for candidate in used_candidates
            if candidate.get("dataset_version")
        }
    )
    route_warning = any(
        code in warning
        for warning in summary_warnings
        for code in ("INSUFFICIENT_TRAVEL_TIME", "UNUSABLE_COORDINATE")
    )
    confidence_score = None
    if used_candidates:
        confidence_score = max(
            0,
            min(
                100,
                round(
                    100
                    * verified_count
                    / len(used_candidates)
                    - 10 * approximate_count / len(used_candidates)
                ),
            ),
        )

    return ItineraryGenerationSummary(
        generation_id=generation_id,
        total_estimated_cost=total_cost,
        budget_limit=budget_limit,
        budget_used_percent=budget_percent,
        included_user_places=included,
        missing_user_places=missing,
        candidate_places_count=candidate_places_count,
        warnings=_merge_unique(summary_warnings),
        data_version=",".join(versions) or None,
        planning_mode=planning_mode,
        verified_activities_count=verified_count,
        approximate_coordinate_count=approximate_count,
        route_provider=settings.ROUTING_PROVIDER,
        route_validation_status="warning" if route_warning else ("passed" if used_candidates else "not_run"),
        confidence_score=confidence_score,
        destination_topology=destination_topology,
        user_request_coverage=UserRequestCoverage(
            required_total=len(must_visit),
            scheduled_total=len(must_visit) - len(missing),
            items=coverage_items,
        ),
        generation_timings_ms=generation_timings_ms or {},
        fallback_reason=fallback_reason,
    )


def _resolve_location_id(activity: dict, candidates_by_ref: dict[str, dict]) -> uuid.UUID | None:
    ref = activity.get("location_ref")
    candidate = candidates_by_ref.get(ref) if ref else None
    location_id = candidate.get("location_id") if candidate else None
    if not location_id:
        return None
    try:
        return uuid.UUID(location_id)
    except (TypeError, ValueError):
        return None


def _merge_activity_notes(activity: dict) -> str | None:
    parts = [
        activity.get("notes"),
        activity.get("reason"),
        activity.get("travel_note"),
    ]
    text = " | ".join(str(part).strip() for part in parts if part)
    return text or None
