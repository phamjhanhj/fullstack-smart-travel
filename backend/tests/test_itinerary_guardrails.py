from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.schemas.day_plan import GenerateDaysRequest
from app.schemas.trip import CreateTripRequest, UpdateTripRequest
from app.services.activity_service import _ensure_itinerary_within_budget, generate_day_plans
from app.services.itinerary_policy import build_itinerary_preflight
from app.services.trip_service import update_trip


def _trip(days: int, budget: int | None = 5_000_000, travelers: int = 2) -> SimpleNamespace:
    start = date(2026, 8, 1)
    return SimpleNamespace(
        id="trip-1",
        user_id="user-1",
        title="Guardrail trip",
        destination="Da Nang",
        start_date=start,
        end_date=start + timedelta(days=days - 1),
        budget=budget,
        num_travelers=travelers,
        status="draft",
    )


def test_create_trip_accepts_90_days_and_rejects_91_days() -> None:
    start = date(2026, 1, 1)
    valid = CreateTripRequest(
        title="90 days",
        destination="Viet Nam",
        start_date=start,
        end_date=start + timedelta(days=89),
    )
    assert (valid.end_date - valid.start_date).days + 1 == 90

    with pytest.raises(ValidationError, match="TRIP_DURATION_TOO_LONG"):
        CreateTripRequest(
            title="91 days",
            destination="Viet Nam",
            start_date=start,
            end_date=start + timedelta(days=90),
        )


def test_budget_storage_guard_rejects_trillion_but_accepts_small_manual_budget() -> None:
    base = {
        "title": "Budget",
        "destination": "Hue",
        "start_date": date(2026, 8, 1),
        "end_date": date(2026, 8, 2),
    }
    assert CreateTripRequest(**base, budget=1_000).budget == 1_000
    with pytest.raises(ValidationError):
        CreateTripRequest(**base, budget=1_000_000_000_000)


def test_ai_preflight_rejects_over_seven_days_but_manual_preflight_allows_it() -> None:
    trip = _trip(days=8, budget=None)
    ai_result = build_itinerary_preflight(trip, GenerateDaysRequest(ai=True))
    manual_result = build_itinerary_preflight(trip, GenerateDaysRequest(ai=False))

    assert ai_result.can_generate is False
    assert ai_result.blocking_issues[0].code == "AI_DURATION_TOO_LONG"
    assert manual_result.can_generate is True


def test_ai_preflight_rejects_one_thousand_vnd_with_minimum_breakdown() -> None:
    result = build_itinerary_preflight(_trip(days=3, budget=1_000), GenerateDaysRequest(ai=True))

    budget_issue = next(issue for issue in result.blocking_issues if issue.code == "BUDGET_INFEASIBLE")
    assert result.can_generate is False
    assert budget_issue.minimum == result.minimum_budget
    assert result.minimum_total_cost == sum(result.cost_breakdown.model_dump().values())
    assert result.minimum_budget > 1_000


@pytest.mark.asyncio
async def test_generation_guard_runs_before_any_database_or_ai_work() -> None:
    class FailOnDatabaseAccess:
        async def execute(self, _statement):
            raise AssertionError("database should not be queried")

    with pytest.raises(AppError) as exc_info:
        await generate_day_plans(
            FailOnDatabaseAccess(),
            _trip(days=8, budget=None),
            GenerateDaysRequest(ai=True),
            SimpleNamespace(id="user-1"),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.data["code"] == "AI_DURATION_TOO_LONG"


def test_required_costs_are_not_scaled_to_an_impossible_budget() -> None:
    itinerary = {
        "days": [
            {
                "day_number": 1,
                "activities": [
                    {"title": "Di chuyen", "estimated_cost": 500_000},
                    {"title": "An uong", "estimated_cost": 320_000},
                ],
            }
        ]
    }

    with pytest.raises(AppError) as exc_info:
        _ensure_itinerary_within_budget(itinerary, 1_000, "strict")

    assert exc_info.value.data["code"] == "BUDGET_INFEASIBLE"
    assert [item["estimated_cost"] for item in itinerary["days"][0]["activities"]] == [500_000, 320_000]


@pytest.mark.asyncio
async def test_partial_date_update_cannot_expand_trip_past_90_days() -> None:
    trip = _trip(days=3)
    trip._access_role = "owner"
    trip._access_type = "owner"

    with pytest.raises(AppError) as exc_info:
        await update_trip(
            None,
            trip,
            UpdateTripRequest(end_date=trip.start_date + timedelta(days=90)),
            SimpleNamespace(id="user-1"),
        )

    assert exc_info.value.data["code"] == "TRIP_DURATION_TOO_LONG"
