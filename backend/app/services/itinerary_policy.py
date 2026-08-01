"""Deterministic input and affordability checks for itinerary generation."""
from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass

from app.core.exceptions import AppError
from app.core.trip_limits import MAX_SYNC_AI_DAYS, MAX_TRIP_DURATION_DAYS
from app.models.trip import Trip
from app.schemas.day_plan import (
    GenerateDaysRequest,
    ItineraryMinimumCostBreakdown,
    ItineraryPreflightIssue,
    ItineraryPreflightResponse,
)


@dataclass(frozen=True)
class MinimumTripCost:
    transport: int
    lodging: int
    meals: int
    required_places: int = 0

    @property
    def total(self) -> int:
        return self.transport + self.lodging + self.meals + self.required_places


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    return "".join(character for character in normalized if unicodedata.category(character) != "Mn").replace("đ", "d")


def _transport_cost_per_leg(travelers: int, payload: GenerateDaysRequest) -> int:
    transport_text = _normalize_text(f"{payload.arrival_transport or ''} {payload.transport_mode or ''}")
    if "may bay" in transport_text or "flight" in transport_text:
        return 1_200_000 * travelers
    if "o to" in transport_text or "car" in transport_text:
        return 350_000 * travelers
    if "xe may" in transport_text or "motorbike" in transport_text:
        return 180_000 * travelers
    if "tau" in transport_text:
        return 350_000 * travelers
    return 250_000 * travelers


def estimate_minimum_trip_cost(trip: Trip, payload: GenerateDaysRequest) -> MinimumTripCost:
    days = (trip.end_date - trip.start_date).days + 1
    travelers = max(int(trip.num_travelers or 1), 1)
    rooms = max(math.ceil(travelers / 2), 1)
    nights = max(days - 1, 0)
    return MinimumTripCost(
        transport=_transport_cost_per_leg(travelers, payload) * 2,
        lodging=250_000 * rooms * nights,
        meals=320_000 * travelers * days,
    )


def _budget_factor(mode: str) -> float:
    if mode == "comfort":
        return 1.3
    if mode == "flexible_15":
        return 1.15
    return 1.0


def build_itinerary_preflight(trip: Trip, payload: GenerateDaysRequest) -> ItineraryPreflightResponse:
    duration_days = (trip.end_date - trip.start_date).days + 1
    estimate = estimate_minimum_trip_cost(trip, payload)
    minimum_budget = math.ceil(estimate.total / _budget_factor(payload.budget_mode))
    issues: list[ItineraryPreflightIssue] = []

    if duration_days not in range(1, MAX_TRIP_DURATION_DAYS + 1):
        issues.append(
            ItineraryPreflightIssue(
                code="TRIP_DURATION_TOO_LONG",
                field="end_date",
                message=(
                    f"Chuyến đi tối đa {MAX_TRIP_DURATION_DAYS} ngày. "
                    "Hãy rút ngắn thời gian hoặc chia thành nhiều chuyến."
                ),
                actual=duration_days,
                maximum=MAX_TRIP_DURATION_DAYS,
                actions=["shorten_trip", "split_trip"],
            )
        )
    elif payload.ai and duration_days > MAX_SYNC_AI_DAYS:
        issues.append(
            ItineraryPreflightIssue(
                code="AI_DURATION_TOO_LONG",
                field="end_date",
                message=(
                    f"AI hiện tạo chi tiết tối đa {MAX_SYNC_AI_DAYS} ngày mỗi lần. "
                    "Hãy rút ngắn hoặc tạo chuyến đi thủ công."
                ),
                actual=duration_days,
                maximum=MAX_SYNC_AI_DAYS,
                actions=["shorten_trip", "create_manual"],
            )
        )

    if payload.ai and trip.budget is not None and trip.budget < minimum_budget:
        issues.append(
            ItineraryPreflightIssue(
                code="BUDGET_INFEASIBLE",
                field="budget",
                message=(
                    f"Ngân sách {trip.budget:,} VND chưa đủ để tạo lịch trình khả thi. "
                    f"Mức tối thiểu ước tính là {minimum_budget:,} VND."
                ).replace(",", "."),
                actual=trip.budget,
                minimum=minimum_budget,
                actions=["increase_budget", "remove_budget", "create_manual"],
            )
        )

    return ItineraryPreflightResponse(
        can_generate=not issues,
        duration_days=duration_days,
        budget=trip.budget,
        minimum_budget=minimum_budget if payload.ai else None,
        minimum_total_cost=estimate.total if payload.ai else 0,
        cost_breakdown=ItineraryMinimumCostBreakdown(
            transport=estimate.transport if payload.ai else 0,
            lodging=estimate.lodging if payload.ai else 0,
            meals=estimate.meals if payload.ai else 0,
            required_places=estimate.required_places if payload.ai else 0,
        ),
        blocking_issues=issues,
        warnings=[],
    )


def validate_itinerary_preflight(trip: Trip, payload: GenerateDaysRequest) -> ItineraryPreflightResponse:
    result = build_itinerary_preflight(trip, payload)
    if result.blocking_issues:
        issue = result.blocking_issues[0]
        raise AppError(
            issue.message,
            status_code=422,
            data={
                **issue.model_dump(),
                "duration_days": result.duration_days,
                "minimum_budget": result.minimum_budget,
                "minimum_total_cost": result.minimum_total_cost,
                "cost_breakdown": result.cost_breakdown.model_dump(),
            },
        )
    return result
