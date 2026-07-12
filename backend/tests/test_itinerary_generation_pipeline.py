from __future__ import annotations

from datetime import date
from uuid import uuid4

from app.services.activity_service import (
    _apply_realistic_costs,
    _build_generation_summary,
    _budget_cap,
    _enrich_experience_route,
    _enforce_closed_loop_itinerary,
    _extract_requested_places_from_preferences,
    _filter_avoided_candidates,
    _fit_itinerary_to_budget,
    _trim_optional_experiences_to_budget,
    _validate_itinerary,
)
from app.schemas.day_plan import GenerateDaysRequest
from app.models.trip import Trip


def _candidate(ref: str, name: str, lat: float, lng: float, score: int = 50, must: str | None = None) -> dict:
    return {
        "ref": ref,
        "location_id": str(uuid4()),
        "name": name,
        "address": "Test address",
        "lat": lat,
        "lng": lng,
        "category": "attraction",
        "score": score,
        "must_visit_match": must,
    }


def _food(ref: str, name: str, category: str = "restaurant") -> dict:
    return {
        "ref": ref,
        "location_id": str(uuid4()),
        "name": name,
        "address": "Food address",
        "lat": 22.8,
        "lng": 104.98,
        "category": category,
        "score": 20,
        "must_visit_match": None,
    }


def _ha_giang_trip(days: int = 3, budget: int = 3_500_000) -> Trip:
    return Trip(
        id=uuid4(),
        user_id=uuid4(),
        title="Ha Giang",
        destination="Ha Giang",
        start_date=date(2026, 7, 18),
        end_date=date(2026, 7, 18 + days - 1),
        budget=budget,
        num_travelers=2,
    )


def test_extract_requested_places_from_preferences() -> None:
    places = _extract_requested_places_from_preferences(
        "Tam bien My Khe, check-in Cau Vang Ba Na Hills, an mi Quang"
    )

    assert "my khe" in places
    assert "cau vang ba na hills" in places


def test_generate_days_request_accepts_planning_options() -> None:
    payload = GenerateDaysRequest(
        overwrite=True,
        must_visit=["My Khe"],
        avoid_places=["Cho dem"],
        interest_weights={"foodie": 12, "culture": 4},
        budget_mode="strict",
        prioritize_user_places="high",
        transport_mode="taxi",
        departure_time="18:00",
        estimated_travel_hours=6,
        daily_start_time="08:30",
        daily_end_time="21:00",
    )

    assert payload.interest_weights == {"foodie": 10, "culture": 4}
    assert payload.budget_mode == "strict"
    assert payload.transport_mode == "taxi"
    assert payload.departure_time == "18:00"
    assert payload.estimated_travel_hours == 6


def test_filter_avoided_candidates_uses_normalized_text() -> None:
    candidates = [
        {"name": "Cho dem Da Nang", "address": "Da Nang"},
        {"name": "My Khe Beach", "address": "Vo Nguyen Giap"},
    ]

    filtered = _filter_avoided_candidates(candidates, ["Chợ đêm"])

    filtered = _filter_avoided_candidates(candidates, ["Cho dem"])

    assert [item["name"] for item in filtered] == ["My Khe Beach"]


def test_closed_loop_enrichment_adds_arrival_lodging_and_return() -> None:
    trip = Trip(
        id=uuid4(),
        user_id=uuid4(),
        title="Ha Giang",
        destination="Ha Giang",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 2),
        budget=4_000_000,
        num_travelers=2,
    )
    payload = GenerateDaysRequest(
        overwrite=True,
        departure_location="Ha Noi",
        arrival_transport="xe khach",
    )
    data = {"days": [{"day_number": 1, "activities": []}, {"day_number": 2, "activities": []}]}

    _enforce_closed_loop_itinerary(data, trip, [], 2, payload)
    _fit_itinerary_to_budget(data, trip.budget, payload.budget_mode)

    titles = [
        activity["title"]
        for day in data["days"]
        for activity in day["activities"]
    ]

    assert any("Ha Noi" in title and "Ha Giang" in title for title in titles)
    assert any("homestay" in title.lower() or "khach san" in title.lower() for title in titles)
    assert any("Di chuyen roi" in title or "ve lai" in title for title in titles)


def test_closed_loop_scheduler_splits_cross_midnight_arrival() -> None:
    trip = Trip(
        id=uuid4(),
        user_id=uuid4(),
        title="Ha Giang",
        destination="Ha Giang",
        start_date=date(2026, 7, 18),
        end_date=date(2026, 7, 20),
        budget=3_500_000,
        num_travelers=2,
    )
    payload = GenerateDaysRequest(
        overwrite=True,
        departure_location="Ha Noi",
        departure_time="18:00",
        estimated_travel_hours=6,
        arrival_transport="xe khach",
    )
    data = {
        "days": [
            {"day_number": 1, "activities": []},
            {"day_number": 2, "activities": []},
            {"day_number": 3, "activities": []},
        ]
    }

    _enforce_closed_loop_itinerary(data, trip, [], 3, payload)

    day1 = data["days"][0]["activities"]
    day2 = data["days"][1]["activities"]

    assert any(
        activity["type"] == "transport"
        and activity["start_time"] == "18:00"
        and activity["end_time"] == "23:59"
        for activity in day1
    )
    assert any(
        "Nhan phong" in activity["title"]
        and activity["start_time"] == "00:00"
        for activity in day2
    )
    assert all(activity["end_time"] > activity["start_time"] for day in data["days"] for activity in day["activities"])


def test_experience_route_groups_three_near_attractions_on_full_day() -> None:
    trip = _ha_giang_trip()
    payload = GenerateDaysRequest(
        overwrite=True,
        departure_location="Ha Noi",
        departure_time="18:00",
        estimated_travel_hours=6,
        pace="balanced",
    )
    candidates = [
        _candidate("p1", "Cot moc so 0", 22.802, 104.980, 90),
        _candidate("p2", "Nui Cam", 22.806, 104.982, 80),
        _candidate("p3", "Quang truong Ha Giang", 22.804, 104.978, 70),
        _candidate("p4", "Bao tang tinh", 22.805, 104.979, 60),
        _food("p5", "Quan an sang"),
        _food("p6", "Cafe toi", "cafe"),
    ]
    data = {"days": [{"day_number": i, "activities": []} for i in range(1, 4)]}

    _enforce_closed_loop_itinerary(data, trip, candidates, 3, payload)
    _enrich_experience_route(data, trip, candidates, 3, payload)

    day2_attractions = [
        activity for activity in data["days"][1]["activities"]
        if activity["type"] == "attraction"
    ]

    assert len(day2_attractions) == 3
    assert "p1" in {activity["location_ref"] for activity in day2_attractions}


def test_experience_route_does_not_overpack_far_attractions() -> None:
    trip = _ha_giang_trip()
    payload = GenerateDaysRequest(
        overwrite=True,
        departure_location="Ha Noi",
        departure_time="18:00",
        estimated_travel_hours=6,
        pace="balanced",
    )
    candidates = [
        _candidate("p1", "Diem trung tam", 22.802, 104.980, 90),
        _candidate("p2", "Diem xa 1", 22.950, 104.980, 80),
        _candidate("p3", "Diem xa 2", 23.100, 104.980, 70),
        _food("p4", "Quan an sang"),
    ]
    data = {"days": [{"day_number": i, "activities": []} for i in range(1, 4)]}

    _enforce_closed_loop_itinerary(data, trip, candidates, 3, payload)
    _enrich_experience_route(data, trip, candidates, 3, payload)

    day2_attractions = [
        activity for activity in data["days"][1]["activities"]
        if activity["type"] == "attraction"
    ]

    assert len(day2_attractions) == 1


def test_experience_route_prioritizes_must_visit_over_score() -> None:
    trip = _ha_giang_trip()
    payload = GenerateDaysRequest(
        overwrite=True,
        departure_location="Ha Noi",
        departure_time="18:00",
        estimated_travel_hours=6,
        pace="relaxed",
    )
    candidates = [
        _candidate("p1", "Diem diem cao", 22.802, 104.980, 100),
        _candidate("p2", "Diem bat buoc", 22.803, 104.981, 10, "Diem bat buoc"),
    ]
    data = {"days": [{"day_number": i, "activities": []} for i in range(1, 4)]}

    _enforce_closed_loop_itinerary(data, trip, candidates, 3, payload)
    _enrich_experience_route(data, trip, candidates, 3, payload)

    day2_attractions = [
        activity for activity in data["days"][1]["activities"]
        if activity["type"] == "attraction"
    ]

    assert day2_attractions[0]["location_ref"] == "p2"


def test_experience_route_respects_arrival_rest_before_sightseeing() -> None:
    trip = _ha_giang_trip()
    payload = GenerateDaysRequest(
        overwrite=True,
        departure_location="Ha Noi",
        departure_time="18:00",
        estimated_travel_hours=6,
        pace="balanced",
    )
    candidates = [
        _candidate("p1", "Cot moc so 0", 22.802, 104.980, 90),
        _candidate("p2", "Nui Cam", 22.806, 104.982, 80),
        _food("p3", "Quan an sang"),
    ]
    data = {"days": [{"day_number": i, "activities": []} for i in range(1, 4)]}

    _enforce_closed_loop_itinerary(data, trip, candidates, 3, payload)
    _enrich_experience_route(data, trip, candidates, 3, payload)

    day2_attractions = [
        activity for activity in data["days"][1]["activities"]
        if activity["type"] == "attraction"
    ]

    assert day2_attractions
    assert all(activity["start_time"] >= "09:15" for activity in day2_attractions)


def test_strict_budget_trims_optional_experiences_but_keeps_must_visit() -> None:
    trip = _ha_giang_trip(budget=1_500_000)
    payload = GenerateDaysRequest(
        overwrite=True,
        departure_location="Ha Noi",
        departure_time="18:00",
        estimated_travel_hours=6,
        pace="balanced",
        budget_mode="strict",
    )
    candidates = [
        _candidate("p1", "Diem bat buoc", 22.802, 104.980, 90, "Diem bat buoc"),
        _candidate("p2", "Diem gan 1", 22.806, 104.982, 80),
        _candidate("p3", "Diem gan 2", 22.804, 104.978, 70),
        _candidate("p4", "Diem gan 3", 22.805, 104.979, 60),
        _food("p5", "Quan an sang"),
    ]
    candidates_by_ref = {candidate["ref"]: candidate for candidate in candidates}
    data = {"days": [{"day_number": i, "activities": []} for i in range(1, 4)]}

    _enforce_closed_loop_itinerary(data, trip, candidates, 3, payload)
    _enrich_experience_route(data, trip, candidates, 3, payload)
    _apply_realistic_costs(data, trip, payload.budget_mode)
    warning = _trim_optional_experiences_to_budget(data, trip.budget, payload.budget_mode, candidates_by_ref, payload)

    attraction_refs = {
        activity["location_ref"]
        for day in data["days"]
        for activity in day["activities"]
        if activity["type"] == "attraction"
    }

    assert warning is not None
    assert "p1" in attraction_refs
    assert len(attraction_refs) < 4


def test_validate_requires_location_ref_and_rejects_overlap() -> None:
    data = {
        "days": [
            {
                "day_number": 1,
                "activities": [
                    {
                        "title": "Museum",
                        "type": "attraction",
                        "start_time": "09:00",
                        "end_time": "11:00",
                        "estimated_cost": 0,
                    },
                    {
                        "title": "Lunch",
                        "type": "meal",
                        "location_ref": "p1",
                        "start_time": "10:30",
                        "end_time": "12:00",
                        "estimated_cost": 100000,
                    },
                ],
            }
        ]
    }

    errors = _validate_itinerary(
        data,
        total_days=1,
        candidates_by_ref={"p1": {"name": "Lunch"}},
        budget=1_000_000,
    )

    assert any("location_ref" in error for error in errors)
    assert any("overlapping" in error for error in errors)


def test_validate_budget_flexible_cap() -> None:
    data = {
        "days": [
            {
                "day_number": 1,
                "activities": [
                    {
                        "title": "Expensive",
                        "type": "transport",
                        "start_time": "09:00",
                        "end_time": "10:00",
                        "estimated_cost": 1_200_000,
                    }
                ],
            }
        ]
    }

    errors = _validate_itinerary(data, total_days=1, candidates_by_ref={}, budget=1_000_000)

    assert any("budget cap" in error for error in errors)


def test_budget_cap_modes() -> None:
    assert _budget_cap(1_000_000, "strict") == 1_000_000
    assert _budget_cap(1_000_000, "flexible_15") == 1_150_000
    assert _budget_cap(1_000_000, "comfort") == 1_300_000


def test_validate_rejects_missing_required_closed_loop_steps() -> None:
    data = {
        "days": [
            {
                "day_number": 1,
                "activities": [
                    {
                        "title": "Only lunch",
                        "type": "meal",
                        "start_time": "12:00",
                        "end_time": "13:00",
                        "estimated_cost": 100_000,
                    }
                ],
            }
        ]
    }

    errors = _validate_itinerary(data, total_days=1, candidates_by_ref={}, budget=1_000_000)

    assert any("outbound transport" in error for error in errors)
    assert any("checkout" in error for error in errors)


def test_generation_summary_marks_missing_user_places() -> None:
    data = {
        "days": [
            {
                "day_number": 1,
                "activities": [
                    {
                        "title": "My Khe Beach",
                        "type": "attraction",
                        "location_ref": "p1",
                        "estimated_cost": 0,
                    }
                ],
            }
        ]
    }

    summary = _build_generation_summary(
        data,
        candidates_by_ref={"p1": {"must_visit_match": "My Khe"}},
        must_visit=["My Khe", "Ba Na Hills"],
        budget=1_000_000,
        candidate_places_count=3,
        warnings=[],
    )

    assert summary.included_user_places == ["My Khe"]
    assert summary.missing_user_places == ["Ba Na Hills"]
    assert summary.budget_used_percent == 0
