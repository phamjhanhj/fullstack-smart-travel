from __future__ import annotations

from app.services.activity_service import (
    _build_generation_summary,
    _extract_requested_places_from_preferences,
    _validate_itinerary,
)


def test_extract_requested_places_from_preferences() -> None:
    places = _extract_requested_places_from_preferences(
        "Tam bien My Khe, check-in Cau Vang Ba Na Hills, an mi Quang"
    )

    assert "my khe" in places
    assert "cau vang ba na hills" in places


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
