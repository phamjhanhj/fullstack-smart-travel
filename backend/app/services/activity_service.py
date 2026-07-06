"""Business logic - Module 4: Day Plans & Activities."""
from __future__ import annotations

import uuid
from datetime import timedelta
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.models.activity import Activity
from app.models.trip import DayPlan, Trip
from app.models.location import Location
from app.models.user import User
from app.schemas.day_plan import (
    CreateActivityRequest,
    GenerateDaysRequest,
    ItineraryGenerationSummary,
    ReorderActivitiesRequest,
    UpdateActivityRequest,
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


async def generate_day_plans(
    db: AsyncSession,
    trip: Trip,
    payload: GenerateDaysRequest | bool,
) -> tuple[list[DayPlan], ItineraryGenerationSummary]:
    """
    Generate a grounded itinerary:
    location discovery -> AI generation -> validation/repair -> deterministic fallback -> DB save.
    """
    if isinstance(payload, bool):
        payload = GenerateDaysRequest(overwrite=payload)

    total_days = (trip.end_date - trip.start_date).days + 1
    if total_days <= 0:
        raise AppError("Ngay ket thuc phai lon hon hoac bang ngay bat dau", status_code=400)

    existing_count = await db.execute(select(DayPlan).where(DayPlan.trip_id == trip.id))
    if not payload.overwrite and existing_count.scalars().first() is not None:
        raise AppError("Chuyen di da co lich trinh, dung overwrite=true de tao lai", status_code=400)

    user_interests = await _load_user_interests(db, trip.user_id)
    must_visit = _merge_unique(
        [*payload.must_visit, *_extract_requested_places_from_preferences(trip.preferences or "")]
    )[:12]

    from app.services.location_service import discover_itinerary_candidates

    candidates = await discover_itinerary_candidates(
        db,
        destination=trip.destination,
        must_visit=must_visit,
        interests=user_interests,
    )
    candidates_by_ref = {item["ref"]: item for item in candidates if item.get("ref")}

    itinerary_data: dict | None = None
    validation_errors: list[str] = []

    if candidates:
        from app.services.ai_service import generate_grounded_itinerary_with_ai

        for _attempt in range(3):
            try:
                itinerary_data = await generate_grounded_itinerary_with_ai(
                    trip,
                    candidates,
                    pace=payload.pace,
                    must_visit=must_visit,
                    interests=user_interests,
                    validation_errors=validation_errors,
                )
                itinerary_data = _sanitize_itinerary(itinerary_data, total_days, candidates_by_ref)
                validation_errors = _validate_itinerary(
                    itinerary_data,
                    total_days=total_days,
                    candidates_by_ref=candidates_by_ref,
                    budget=trip.budget,
                )
                if not validation_errors:
                    break
            except AppError as exc:
                validation_errors = [str(exc)]
                itinerary_data = None
                break

    if itinerary_data is None or validation_errors:
        itinerary_data = _build_fallback_itinerary(
            trip,
            candidates,
            total_days=total_days,
            pace=payload.pace,
        )
        validation_errors = _validate_itinerary(
            itinerary_data,
            total_days=total_days,
            candidates_by_ref=candidates_by_ref,
            budget=trip.budget,
        )
        if validation_errors:
            _fit_itinerary_to_budget(itinerary_data, trip.budget)

    summary = _build_generation_summary(
        itinerary_data,
        candidates_by_ref=candidates_by_ref,
        must_visit=must_visit,
        budget=trip.budget,
        candidate_places_count=len(candidates),
        warnings=validation_errors,
    )

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

    await db.commit()
    for day in new_days:
        await db.refresh(day)

    return new_days, summary


async def _load_user_interests(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    prefs = user.preferences_json if user else None
    if not isinstance(prefs, dict):
        return []
    interests = prefs.get("interests") or []
    return [str(item).strip().lower() for item in interests if str(item).strip()]


def _extract_requested_places_from_preferences(preferences: str) -> list[str]:
    if not preferences:
        return []
    chunks = re.split(r"[,;\n]+", preferences)
    places: list[str] = []
    action_words = (
        "di ",
        "den ",
        "ghe ",
        "tham quan",
        "check-in",
        "check in",
        "tam bien",
        "chinh phuc",
        "kham pha",
    )
    for chunk in chunks:
        text = chunk.strip(" .:-")
        if not 3 <= len(text) <= 80:
            continue
        normalized = _normalize_text(text)
        if any(word in normalized for word in action_words):
            cleaned = re.sub(
                r"^(di|den|ghe|tham quan|check-in|check in|tam bien|chinh phuc|kham pha)\s+",
                "",
                normalized,
            ).strip()
            places.append(cleaned or text)
        elif any(ch.isupper() for ch in text[1:]):
            places.append(text)
    return _merge_unique(places)


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


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


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
) -> list[str]:
    errors: list[str] = []
    days = data.get("days") if isinstance(data, dict) else []
    if not isinstance(days, list) or len(days) != total_days:
        return [f"Expected exactly {total_days} days."]

    total_cost = 0
    attraction_count = 0
    place_based_types = {"meal", "attraction", "hotel"}

    for day in days:
        intervals: list[tuple[int, int]] = []
        for activity in day.get("activities", []):
            activity_type = _sanitize_type(activity.get("type"))
            title = activity.get("title") or "activity"
            if activity_type in place_based_types and candidates_by_ref and not activity.get("location_ref"):
                errors.append(f"Activity '{title}' needs a valid location_ref.")
            if activity.get("location_ref") and activity["location_ref"] not in candidates_by_ref:
                errors.append(f"Unknown location_ref {activity.get('location_ref')}.")
            if activity_type == "attraction":
                attraction_count += 1
            total_cost += _sanitize_cost(activity.get("estimated_cost")) or 0
            start = _minutes(activity.get("start_time"))
            end = _minutes(activity.get("end_time"))
            if start is None or end is None or end <= start:
                errors.append(f"Activity '{title}' has invalid time.")
                continue
            if any(start < old_end and end > old_start for old_start, old_end in intervals):
                errors.append(f"Day {day.get('day_number')} has overlapping activities.")
            intervals.append((start, end))

    if budget and total_cost > int(budget * 1.15):
        errors.append("Total estimated cost is over the flexible 15 percent budget cap.")

    minimum_attractions = min(max(total_days, 2), 5)
    if candidates_by_ref and attraction_count < minimum_attractions:
        errors.append(f"Expected at least {minimum_attractions} attraction activities.")

    return errors[:8]


def _minutes(value: str | None) -> int | None:
    value = _sanitize_time(value)
    if not value:
        return None
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


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
        "notes": None,
    }


def _simple_activity(title: str, activity_type: str, start: str, end: str, cost: int, location_ref: str | None) -> dict:
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
        "notes": None,
    }


def _fit_itinerary_to_budget(data: dict, budget: int | None) -> None:
    if not budget:
        return
    cap = int(budget * 1.15)
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


def _build_generation_summary(
    data: dict,
    *,
    candidates_by_ref: dict[str, dict],
    must_visit: list[str],
    budget: int | None,
    candidate_places_count: int,
    warnings: list[str],
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

    budget_limit = int(budget * 1.15) if budget else None
    budget_percent = round((total_cost / budget) * 100) if budget else None
    summary_warnings = list(warnings)
    if missing:
        summary_warnings.append("Mot so dia diem nguoi dung muon di chua duoc dua vao lich trinh.")
    if budget_limit and total_cost > budget_limit:
        summary_warnings.append("Tong chi phi uoc tinh vuot qua muc linh hoat 15%.")

    return ItineraryGenerationSummary(
        total_estimated_cost=total_cost,
        budget_limit=budget_limit,
        budget_used_percent=budget_percent,
        included_user_places=included,
        missing_user_places=missing,
        candidate_places_count=candidate_places_count,
        warnings=_merge_unique(summary_warnings),
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
