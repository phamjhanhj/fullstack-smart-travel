from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.public_trip import PublicTripPublication
from app.schemas.public_trip import PublicTripImportRequest, UpsertPublicTripRequest
from app.services.public_trip_service import (
    _privacy_issues,
    _snapshot_privacy_issues,
    _selected_snapshot_activities,
    _slugify,
)


def _publication() -> PublicTripPublication:
    return PublicTripPublication(
        id=uuid4(),
        source_trip_id=uuid4(),
        author_user_id=uuid4(),
        slug="da-nang-3-ngay",
        title="Đà Nẵng 3 ngày",
        summary="Lịch trình thực tế",
        destination="Đà Nẵng",
        duration_days=2,
        snapshot_json={
            "days": [
                {
                    "day_number": 1,
                    "activities": [
                        {"source_activity_id": "a1", "title": "Mỹ Khê", "actual_cost": 0},
                    ],
                },
                {
                    "day_number": 2,
                    "activities": [
                        {"source_activity_id": "a2", "title": "Cầu Vàng", "actual_cost": 750000},
                    ],
                },
            ]
        },
    )


def test_slugify_vietnamese_title() -> None:
    assert _slugify("Lịch trình Đà Nẵng 3 ngày") == "lich-trinh-da-nang-3-ngay"


def test_privacy_scan_blocks_contact_information() -> None:
    payload = UpsertPublicTripRequest(
        title="Đà Nẵng thực tế",
        summary="Liên hệ tôi qua 0912345678 để lấy mã đặt chỗ.",
        author_confirmed=True,
    )

    issues = _privacy_issues(payload)

    assert any(issue["code"] == "PHONE_DETECTED" for issue in issues)


def test_privacy_scan_checks_activity_data_in_final_snapshot() -> None:
    issues = _snapshot_privacy_issues(
        {
            "days": [
                {
                    "activities": [
                        {
                            "title": "Hotel",
                            "description": "Booking: ABCDE-12345",
                            "address": "Da Nang",
                        }
                    ]
                }
            ]
        }
    )

    assert any(issue["code"] == "BOOKING_CODE_DETECTED" for issue in issues)

    formatted_phone_issues = _snapshot_privacy_issues(
        {"days": [{"activities": [{"description": "Liên hệ 0912 345 678"}]}]}
    )
    assert any(issue["code"] == "PHONE_DETECTED" for issue in formatted_phone_issues)


def test_select_single_public_activity_for_partial_import() -> None:
    payload = PublicTripImportRequest(
        import_mode="activity",
        target_trip_id=uuid4(),
        target_day_plan_id=uuid4(),
        source_activity_ids=["a2"],
    )

    selected = _selected_snapshot_activities(_publication(), payload)

    assert len(selected) == 1
    assert selected[0][0] == 2
    assert selected[0][1]["title"] == "Cầu Vàng"


def test_full_trip_import_requires_new_start_date() -> None:
    with pytest.raises(ValidationError):
        PublicTripImportRequest(import_mode="full_trip")

    valid = PublicTripImportRequest(
        import_mode="full_trip",
        start_date=date(2026, 9, 10),
    )
    assert valid.start_date == date(2026, 9, 10)
