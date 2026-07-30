from __future__ import annotations

from datetime import date
from uuid import uuid4
import asyncio

import pytest

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.trip import Trip
from app.services import ai_service
from app.services import location_service
from app.services.itinerary_verifier import verify_grounded_itinerary
from app.services.location_service import _explore_categories, _rank_dataset_search
from app.models.location import Location
from app.services.place_data_service import (
    coordinate_quality,
    normalize_category,
    normalize_place,
    stable_location_id,
)
from app.services.province_service import province_search_names


def test_category_and_stable_id_normalization() -> None:
    assert normalize_category("ẩm thực & giải trí") == "restaurant"
    assert normalize_category("homestay") == "homestay"
    assert normalize_category("giải trí") == "entertainment"
    assert stable_location_id("dataset-a", "place-1") == stable_location_id("dataset-a", "place-1")
    assert stable_location_id("dataset-a", "place-1") != stable_location_id("dataset-b", "place-1")


def test_coordinate_quality_quarantines_obvious_errors() -> None:
    assert coordinate_quality(None, 105.0)[0] == "missing"
    status, _, flags = coordinate_quality(22.1436, 22.1436)
    assert status == "suspicious"
    assert "outside_vietnam_bbox" in flags
    assert "lat_equals_lng" in flags
    assert coordinate_quality(16.0544, 108.2022)[0] == "approximate"


def test_normalize_place_marks_unverified_or_forbidden_records_for_review() -> None:
    meta = {
        "dataset_id": "vn-test-attractions",
        "schema_version": "1.0",
        "province_code": "DN",
        "province_name": "Đà Nẵng",
    }
    place = {
        "id": "dn-test-001",
        "name": "Điểm thử",
        "category": "attraction",
        "address": "Đà Nẵng",
        "lat": 16.0544,
        "lng": 108.2022,
        "verification": {"status": "unverified", "confidence": "medium"},
        "constraints": {"avoid_auto_schedule": True},
    }

    row, flags = normalize_place(meta, place)

    assert flags == []
    assert row is not None
    assert row["status"] == "needs_review"
    assert row["coordinate_status"] == "approximate"
    assert row["category"] == "attraction"


def test_province_alias_supports_current_and_legacy_destinations() -> None:
    assert province_search_names("Tuyên Quang") == ["Tuyên Quang", "Hà Giang"]
    assert province_search_names("Hà Giang") == ["Hà Giang"]
    assert province_search_names("TP HCM") == [
        "Thành phố Hồ Chí Minh",
        "Bình Dương",
        "Bà Rịa - Vũng Tàu",
    ]


def test_explore_category_mapping_includes_lodging_variants() -> None:
    assert _explore_categories("meal") == ["restaurant"]
    assert set(_explore_categories("hotel")) == {
        "hotel", "homestay", "resort", "hostel", "guesthouse",
    }
    assert set(_explore_categories("attraction")) == {"attraction", "entertainment"}


def test_local_search_matches_vietnamese_with_or_without_accents() -> None:
    locations = [
        Location(
            name="Bảo tàng Điêu khắc Chăm Đà Nẵng",
            address="Hải Châu, Đà Nẵng",
            category="attraction",
            tags=["culture", "museum"],
            data_confidence="high",
            coordinate_status="approximate",
        ),
        Location(
            name="Nhà hàng Biển",
            address="Sơn Trà, Đà Nẵng",
            category="restaurant",
            tags=["seafood"],
            data_confidence="high",
            coordinate_status="approximate",
        ),
    ]

    matches = _rank_dataset_search(locations, "bao tang cham", limit=10)

    assert [location.name for location in matches] == [
        "Bảo tàng Điêu khắc Chăm Đà Nẵng"
    ]


@pytest.mark.asyncio
async def test_verifier_detects_opening_hours_and_route_conflicts() -> None:
    candidates = {
        "p1": {
            "name": "Museum",
            "lat": 16.05,
            "lng": 108.20,
            "coordinate_status": "approximate",
            "opening_hours": {
                "weekly": [{"day": "mon", "open": "08:00", "close": "10:00"}]
            },
            "constraints": {},
        },
        "p2": {
            "name": "Beach",
            "lat": 16.15,
            "lng": 108.30,
            "coordinate_status": "approximate",
            "opening_hours": {
                "weekly": [{"day": "mon", "open": "00:00", "close": "24:00"}]
            },
            "constraints": {"live_check_required": True},
        },
    }
    data = {
        "days": [
            {
                "day_number": 1,
                "activities": [
                    {
                        "title": "Museum",
                        "location_ref": "p1",
                        "start_time": "09:30",
                        "end_time": "10:30",
                    },
                    {
                        "title": "Beach",
                        "location_ref": "p2",
                        "start_time": "10:35",
                        "end_time": "12:00",
                    },
                ],
            }
        ]
    }

    issues = await verify_grounded_itinerary(
        data,
        candidates_by_ref=candidates,
        start_date=date(2026, 7, 20),  # Monday
        transport_mode="car",
    )
    codes = {issue.code for issue in issues}

    assert "OPENING_HOURS_CONFLICT" in codes
    assert "INSUFFICIENT_TRAVEL_TIME" in codes
    assert "APPROXIMATE_COORDINATE" in codes
    assert "LIVE_CHECK_REQUIRED" in codes
    assert data["days"][0]["activities"][1]["route_from_previous"]["duration_minutes"] > 5


@pytest.mark.asyncio
async def test_itinerary_groq_timeout_is_hard_and_does_not_retry(monkeypatch) -> None:
    calls = 0

    async def slow_create(**_kwargs):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.2)

    monkeypatch.setattr(ai_service._groq_client.chat.completions, "create", slow_create)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(settings, "ITINERARY_GROQ_TIMEOUT_SECONDS", 0.01)
    trip = Trip(
        id=uuid4(),
        user_id=uuid4(),
        title="Cao Bang",
        destination="Cao Bang",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 2),
        num_travelers=2,
    )

    with pytest.raises(AppError) as exc_info:
        await ai_service.generate_grounded_itinerary_with_ai(
            trip,
            [{"ref": "p1", "name": "Thac Ban Gioc", "category": "attraction"}],
            pace="balanced",
            must_visit=["Thac Ban Gioc"],
            interests=["nature"],
        )

    assert exc_info.value.status_code == 504
    assert calls == 1


@pytest.mark.asyncio
async def test_generation_candidate_lookup_does_not_use_online_fallback(monkeypatch) -> None:
    async def database_candidates(*_args, **_kwargs):
        return [
            {
                "ref": "",
                "location_id": str(uuid4()),
                "name": "Thac Ban Gioc",
                "category": "attraction",
                "score": 100,
                "must_visit_match": "Thac Ban Gioc",
            }
        ]

    async def forbidden_online_search(*_args, **_kwargs):
        raise AssertionError("online place search must not run during generation")

    monkeypatch.setattr(location_service, "_discover_database_candidates", database_candidates)
    monkeypatch.setattr(location_service, "search_locations", forbidden_online_search)

    candidates = await location_service.discover_itinerary_candidates(
        object(),
        destination="Cao Bang",
        must_visit=["Thac Ban Gioc"],
        allow_external_fallback=False,
    )

    assert [candidate["name"] for candidate in candidates] == ["Thac Ban Gioc"]


@pytest.mark.asyncio
async def test_supported_destinations_require_attraction_food_and_lodging() -> None:
    class FakeResult:
        def all(self):
            return [
                ("Lào Cai", "attraction", 12),
                ("Lào Cai", "restaurant", 8),
                ("Lào Cai", "hotel", 5),
                ("Sparse Province", "attraction", 20),
            ]

    class FakeDb:
        async def execute(self, _statement):
            return FakeResult()

    items = await location_service.list_supported_destinations(FakeDb())

    assert [item["destination"] for item in items] == ["Lào Cai"]
    assert items[0]["can_generate"] is True
    assert items[0]["total_count"] == 25
