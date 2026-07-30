"""Deterministic factual checks for a grounded itinerary."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from app.services.route_service import estimate_route

_DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass(frozen=True)
class ItineraryIssue:
    severity: str
    code: str
    message: str
    day_number: int | None = None
    location_ref: str | None = None
    suggested_action: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def as_prompt_text(self) -> str:
        location = f", location_ref={self.location_ref}" if self.location_ref else ""
        day = f"day {self.day_number}" if self.day_number else "itinerary"
        return f"{self.code} ({day}{location}): {self.message}"


def _minutes(value: Any, *, allow_24: bool = False) -> int | None:
    if not isinstance(value, str) or ":" not in value:
        return None
    try:
        hours, minutes = (int(part) for part in value.split(":", 1))
    except ValueError:
        return None
    if allow_24 and hours == 24 and minutes == 0:
        return 24 * 60
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        return None
    return hours * 60 + minutes


def _opening_window(candidate: dict, activity_date: date) -> tuple[int, int] | None:
    opening_hours = candidate.get("opening_hours")
    if not isinstance(opening_hours, dict):
        return None
    weekly = opening_hours.get("weekly")
    if not isinstance(weekly, list):
        return None
    day_name = _DAY_NAMES[activity_date.weekday()]
    for item in weekly:
        if not isinstance(item, dict) or str(item.get("day", "")).lower() != day_name:
            continue
        if item.get("closed") is True:
            return (0, 0)
        open_min = _minutes(item.get("open"), allow_24=True)
        close_min = _minutes(item.get("close"), allow_24=True)
        if open_min is not None and close_min is not None:
            return open_min, close_min
    return None


def _coords(candidate: dict) -> tuple[float, float] | None:
    try:
        return float(candidate["lat"]), float(candidate["lng"])
    except (KeyError, TypeError, ValueError):
        return None


async def verify_grounded_itinerary(
    data: dict,
    *,
    candidates_by_ref: dict[str, dict],
    start_date: date,
    transport_mode: str,
    required_location_refs: set[str] | None = None,
) -> list[ItineraryIssue]:
    issues: list[ItineraryIssue] = []
    used_location_refs: set[str] = set()
    for day in data.get("days", []):
        day_number = int(day.get("day_number") or 0)
        activity_date = start_date + timedelta(days=max(day_number - 1, 0))
        located_activities: list[tuple[dict, dict]] = []
        for activity in day.get("activities", []):
            ref = activity.get("location_ref")
            if not ref:
                continue
            used_location_refs.add(str(ref))
            candidate = candidates_by_ref.get(ref)
            if not candidate:
                issues.append(
                    ItineraryIssue(
                        "error",
                        "UNKNOWN_LOCATION_REF",
                        "Địa điểm không thuộc candidate snapshot.",
                        day_number,
                        str(ref),
                        "replace",
                    )
                )
                continue
            located_activities.append((activity, candidate))

            coordinate_status = candidate.get("coordinate_status")
            if coordinate_status in {"suspicious", "missing"}:
                issues.append(
                    ItineraryIssue(
                        "error",
                        "UNUSABLE_COORDINATE",
                        "Tọa độ thiếu hoặc đáng ngờ, không được tự động lên lịch.",
                        day_number,
                        ref,
                        "replace",
                    )
                )
            elif coordinate_status == "approximate":
                issues.append(
                    ItineraryIssue(
                        "warning",
                        "APPROXIMATE_COORDINATE",
                        "Tọa độ gần đúng; đã áp dụng thêm thời gian đệm.",
                        day_number,
                        ref,
                    )
                )

            constraints = candidate.get("constraints") or {}
            if constraints.get("avoid_auto_schedule") is True:
                issues.append(
                    ItineraryIssue(
                        "error",
                        "AUTO_SCHEDULE_FORBIDDEN",
                        "Nguồn dữ liệu yêu cầu không tự động lên lịch địa điểm này.",
                        day_number,
                        ref,
                        "replace",
                    )
                )
            if constraints.get("live_check_required") is True:
                issues.append(
                    ItineraryIssue(
                        "warning",
                        "LIVE_CHECK_REQUIRED",
                        "Cần kiểm tra lại tình trạng hoạt động/đặt chỗ trước khi đi.",
                        day_number,
                        ref,
                    )
                )

            window = _opening_window(candidate, activity_date)
            start = _minutes(activity.get("start_time"))
            end = _minutes(activity.get("end_time"))
            if window == (0, 0):
                issues.append(
                    ItineraryIssue(
                        "error",
                        "PLACE_CLOSED",
                        "Địa điểm đóng cửa trong ngày được xếp lịch.",
                        day_number,
                        ref,
                        "move_or_replace",
                    )
                )
            elif window and start is not None and end is not None:
                open_min, close_min = window
                if start < open_min or end > close_min:
                    issues.append(
                        ItineraryIssue(
                            "error",
                            "OPENING_HOURS_CONFLICT",
                            (
                                f"Hoạt động {activity.get('start_time')}-{activity.get('end_time')} "
                                f"nằm ngoài giờ mở cửa."
                            ),
                            day_number,
                            ref,
                            "move_or_replace",
                        )
                    )
            elif not candidate.get("opening_hours"):
                issues.append(
                    ItineraryIssue(
                        "warning",
                        "OPENING_HOURS_UNKNOWN",
                        "Chưa có dữ liệu giờ mở cửa.",
                        day_number,
                        ref,
                    )
                )

        for (previous, first), (current, second) in zip(located_activities, located_activities[1:]):
            first_coords, second_coords = _coords(first), _coords(second)
            if first_coords is None or second_coords is None:
                continue
            previous_end = _minutes(previous.get("end_time"))
            current_start = _minutes(current.get("start_time"))
            if previous_end is None or current_start is None:
                continue
            uncertain = any(
                candidate.get("coordinate_status") == "approximate"
                for candidate in (first, second)
            )
            route = await estimate_route(
                *first_coords,
                *second_coords,
                mode=transport_mode,
                uncertain=uncertain,
                offline_only=True,
            )
            current["route_from_previous"] = {
                "distance_meters": route.distance_meters,
                "duration_minutes": route.duration_minutes,
                "provider": route.provider,
                "approximate": route.approximate,
            }
            available = current_start - previous_end
            if available < route.duration_minutes:
                issues.append(
                    ItineraryIssue(
                        "error",
                        "INSUFFICIENT_TRAVEL_TIME",
                        (
                            f"Chỉ có {max(available, 0)} phút nhưng cần khoảng "
                            f"{route.duration_minutes} phút di chuyển."
                        ),
                        day_number,
                        current.get("location_ref"),
                        "move_later_or_replace",
                    )
                )
    for missing_ref in sorted((required_location_refs or set()) - used_location_refs):
        issues.append(
            ItineraryIssue(
                "error",
                "MUST_VISIT_MISSING",
                "Địa điểm bắt buộc theo yêu cầu người dùng chưa có trong lịch trình.",
                location_ref=missing_ref,
                suggested_action="reschedule_optional_activity",
            )
        )
    return issues
