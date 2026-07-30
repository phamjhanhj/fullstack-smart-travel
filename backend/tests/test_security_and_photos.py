from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.exceptions import AppError
from app.schemas.day_plan import CreateActivityRequest, UpdateActivityRequest
from app.schemas.trip import UpdateTripRequest
from app.schemas.user import UpdateProfileRequest
from app.services import budget_service, trip_service
from app.services.destination_photo_service import _build_photo_details
from app.services.trip_history_service import diff_snapshots, serialize_value


def test_production_rejects_default_jwt_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="dev-secret-key-change-in-production",
            ALLOWED_ORIGINS="http://localhost:4200",
        )


def test_cors_rejects_wildcard_origin() -> None:
    with pytest.raises(ValidationError):
        Settings(ALLOWED_ORIGINS="*")


def test_url_fields_require_http_or_https() -> None:
    with pytest.raises(ValidationError):
        UpdateProfileRequest(avatar_url="javascript:alert(1)")

    with pytest.raises(ValidationError):
        UpdateTripRequest(cover_image_url="ftp://example.com/image.jpg")

    with pytest.raises(ValidationError):
        UpdateActivityRequest(booking_url="javascript:alert(1)")


def test_activity_time_range_and_update_title_are_validated() -> None:
    with pytest.raises(ValidationError):
        CreateActivityRequest(title="Lunch", start_time="12:00", end_time="11:30")

    with pytest.raises(ValidationError):
        UpdateActivityRequest(title="")


def test_trip_update_fields_are_validated() -> None:
    with pytest.raises(ValidationError):
        UpdateTripRequest(title="")

    with pytest.raises(ValidationError):
        UpdateTripRequest(
            start_date=date(2026, 8, 2),
            end_date=date(2026, 8, 1),
        )


@pytest.mark.asyncio
async def test_group_split_uses_num_travelers(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_summary(_db, _trip):
        return {"budget_actual": 900_000, "budget_planned": 1_200_000}

    monkeypatch.setattr(budget_service, "get_trip_summary", fake_summary)
    trip = SimpleNamespace(id="trip-1", num_travelers=3)

    result = await budget_service.get_group_split_summary(None, trip)

    assert result["companions_count"] == 3
    assert result["per_person_actual"] == 300_000
    assert result["per_person_planned"] == 400_000


@pytest.mark.asyncio
async def test_trip_update_rejects_invalid_merged_dates() -> None:
    trip = SimpleNamespace(
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 3),
        status="draft",
    )

    with pytest.raises(AppError) as exc_info:
        await trip_service.update_trip(
            None,
            trip,
            UpdateTripRequest(start_date=date(2026, 8, 4)),
            SimpleNamespace(id="user-1"),
        )

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_trip_cannot_complete_before_end_date() -> None:
    trip = SimpleNamespace(
        start_date=date.today(),
        end_date=date.today() + timedelta(days=1),
        status="active",
    )

    with pytest.raises(AppError) as exc_info:
        await trip_service.update_trip(
            None,
            trip,
            UpdateTripRequest(status="completed"),
            SimpleNamespace(id="user-1"),
        )

    assert exc_info.value.status_code == 422


def test_photo_details_are_backward_compatible_metadata() -> None:
    details = _build_photo_details("Da Nang", ["https://example.com/photo.jpg"], "foursquare")

    assert details[0]["url"] == "https://example.com/photo.jpg"
    assert details[0]["thumbnail_url"] == "https://example.com/photo.jpg"
    assert details[0]["source"] == "foursquare"
    assert details[0]["alt"] == "Travel photo of Da Nang"


def test_trip_history_diff_uses_labels_and_changed_values_only() -> None:
    changes = diff_snapshots(
        {"title": "Old trip", "budget": 1000, "status": "draft"},
        {"title": "New trip", "budget": 1000, "status": "active"},
        {"title": "Ten chuyen di", "status": "Trang thai"},
    )

    assert changes == [
        {"field": "title", "label": "Ten chuyen di", "before": "Old trip", "after": "New trip"},
        {"field": "status", "label": "Trang thai", "before": "draft", "after": "active"},
    ]


def test_trip_history_serialize_value_handles_nested_values() -> None:
    payload = serialize_value({"items": [{"id": "abc", "value": None}]})

    assert payload == {"items": [{"id": "abc", "value": None}]}
